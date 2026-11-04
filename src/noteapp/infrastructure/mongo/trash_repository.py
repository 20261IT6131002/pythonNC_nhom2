"""Versioned tombstones; purge/retention clean attachments only with a configured store."""

import logging
from datetime import datetime
from typing import Any

from pymongo import ReturnDocument
from pymongo.database import Database

from noteapp.application.ports.attachment_store import AttachmentStore
from noteapp.application.ports.trash_repository import TrashedNote, TrashPage
from noteapp.domain.entities.note import Note
from noteapp.domain.errors import (
    AttachmentStoreFailure,
    Conflict,
    NotFound,
    RepositoryUnavailable,
    ValidationError,
)
from noteapp.domain.policies.delete_policy import transition_note
from noteapp.domain.policies.note_validation import utc_datetime, validate_version
from noteapp.infrastructure.mongo.models import (
    attachment_from_document,
    note_from_document,
    object_id,
)
from noteapp.infrastructure.mongo.query_cursor import decode_seek, encode_seek, fingerprint
from noteapp.infrastructure.mongo.repositories import database_errors

TEXT_FIELDS = (
    "_id",
    "client_operation_id",
    "title",
    "content_plain",
    "priority",
    "priority_rank",
    "category_id",
    "version",
    "created_at",
    "updated_at",
    "is_deleted",
    "schema_version",
    "deleted_at",
    "reminder",  # plain data owned by the note; it is deleted together with it
)


LOGGER = logging.getLogger("noteapp.attachments")


def purgeable_fields(allow_attachment: bool) -> tuple[str, ...]:
    return TEXT_FIELDS + ("attachment",) if allow_attachment else TEXT_FIELDS


def text_only_guard(allow_attachment: bool = False) -> dict[str, Any]:
    return {
        "schema_version": {"$in": [1, 2]},
        "$expr": {
            "$and": [
                {
                    "$setIsSubset": [
                        {
                            "$map": {
                                "input": {"$objectToArray": "$$ROOT"},
                                "as": "field",
                                "in": "$$field.k",
                            }
                        },
                        list(purgeable_fields(allow_attachment)),
                    ]
                },
                {"$eq": [{"$type": "$content_plain"}, "string"]},
            ]
        },
    }


def trashed_record(document: dict[str, Any]) -> TrashedNote:
    try:
        return TrashedNote(note_from_document(document), utc_datetime(document.get("deleted_at")))
    except (ValidationError, KeyError, TypeError):
        raise RepositoryUnavailable("Trash record needs independent data repair.") from None


class MongoTrashRepository:
    def __init__(self, database: Database, attachments: AttachmentStore | None = None) -> None:
        self.collection = database.notes
        self.attachments = attachments

    def _read(self, note_id: str, expected_version: int, deleted: bool) -> dict[str, Any]:
        validate_version(expected_version)
        document = self.collection.find_one({"_id": object_id(note_id)})
        if document is None:
            raise NotFound("Note not found.")
        if document.get("version") != expected_version or document.get("is_deleted") is not deleted:
            raise Conflict("Note state or version changed.")
        if type(document.get("schema_version")) is not int or document["schema_version"] not in (
            1,
            2,
        ):
            raise RepositoryUnavailable("Unsupported stored schema.")
        return document

    def _missed(self, note_id: str) -> None:
        if self.collection.find_one({"_id": object_id(note_id)}, {"_id": 1}) is None:
            raise NotFound("Note no longer exists.")
        raise Conflict("Note state or version changed.")

    @database_errors
    def move_to_trash(self, note_id: str, expected_version: int, now: datetime) -> TrashedNote:
        document = self._read(note_id, expected_version, False)
        now = utc_datetime(now)
        updated = transition_note(note_from_document(document), expected_version, False, True, now)
        result = self.collection.find_one_and_update(
            {"_id": document["_id"], "version": expected_version, "is_deleted": False},
            {
                "$set": {
                    "is_deleted": True,
                    "deleted_at": now,
                    "updated_at": updated.updated_at,
                    "schema_version": 2,
                },
                "$inc": {"version": 1},
            },
            return_document=ReturnDocument.AFTER,
        )
        if result is None:
            self._missed(note_id)
        return trashed_record(result)

    @database_errors
    def restore(self, note_id: str, expected_version: int, now: datetime) -> Note:
        document = self._read(note_id, expected_version, True)
        record = trashed_record(document)
        updated = transition_note(record.note, expected_version, True, False, now)
        result = self.collection.find_one_and_update(
            {"_id": document["_id"], "version": expected_version, "is_deleted": True},
            {
                "$set": {"is_deleted": False, "updated_at": updated.updated_at},
                "$unset": {"deleted_at": ""},
                "$inc": {"version": 1},
            },
            return_document=ReturnDocument.AFTER,
        )
        if result is None:
            self._missed(note_id)
        return note_from_document(result)

    @database_errors
    def list_trashed(self, limit: int, cursor: str | None = None) -> TrashPage:
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValidationError("Page size must be between 1 and 100.")
        query = {"is_deleted": True}
        signature = fingerprint({"limit": limit, "sort": "deleted_at_DESC"})
        if cursor is not None:
            keys, note_id = decode_seek(cursor, "trash_list", signature)
            try:
                if len(keys) != 1 or not isinstance(keys[0], str):
                    raise ValueError
                timestamp = utc_datetime(datetime.fromisoformat(keys[0]))
            except (ValueError, TypeError):
                raise ValidationError("Invalid trash timestamp cursor.") from None
            query["$or"] = [
                {"deleted_at": {"$lt": timestamp}},
                {"deleted_at": timestamp, "_id": {"$lt": object_id(note_id)}},
            ]
        documents = list(
            self.collection.find(query).sort([("deleted_at", -1), ("_id", -1)]).limit(limit + 1)
        )
        rows = tuple(trashed_record(document) for document in documents[:limit])
        next_cursor = None
        if len(documents) > limit:
            last = rows[-1]
            next_cursor = encode_seek(
                "trash_list", signature, [last.deleted_at.isoformat()], last.note.id
            )
        return TrashPage(rows, next_cursor)

    def _delete(self, note_id: str, expected_version: int, cutoff: datetime | None = None) -> bool:
        document = self._read(note_id, expected_version, True)
        allowed = purgeable_fields(self.attachments is not None)
        if set(document) - set(allowed) or not isinstance(document.get("content_plain"), str):
            raise ValidationError("Attachment or locked payload needs verified cleanup.")
        record = trashed_record(document)
        reference = attachment_from_document(document.get("attachment"))
        if cutoff is not None and record.deleted_at > cutoff:
            return False
        query = {
            "_id": document["_id"],
            "version": expected_version,
            "is_deleted": True,
            "deleted_at": document["deleted_at"],
            **text_only_guard(self.attachments is not None),
        }
        result = self.collection.delete_one(query)
        if result.deleted_count != 1:
            self._missed(note_id)
        if reference is not None and self.attachments is not None:
            try:
                self.attachments.delete(reference)
            except AttachmentStoreFailure:
                # The note is gone; the reconciler removes the unreferenced payload.
                LOGGER.warning("attachment_cleanup_deferred", extra={"stage": "purge"})
        return True

    @database_errors
    def purge_confirmed(self, note_id: str, expected_version: int) -> None:
        self._delete(note_id, expected_version)

    @database_errors
    def expired_candidates(self, cutoff: datetime, limit: int = 100) -> tuple[TrashedNote, ...]:
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValidationError("Retention batch must be between 1 and 100.")
        query = {
            "is_deleted": True,
            "deleted_at": {"$lte": utc_datetime(cutoff)},
            **text_only_guard(self.attachments is not None),
        }
        return tuple(
            trashed_record(document)
            for document in self.collection.find(query)
            .sort([("deleted_at", 1), ("_id", 1)])
            .limit(limit)
        )

    @database_errors
    def purge_expired(self, note_id: str, expected_version: int, cutoff: datetime) -> bool:
        return self._delete(note_id, expected_version, utc_datetime(cutoff))
