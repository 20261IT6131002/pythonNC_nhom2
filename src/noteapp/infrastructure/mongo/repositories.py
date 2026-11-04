"""Mongo ports with idempotent insert, bounded pages and atomic CAS."""

from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from functools import wraps
from secrets import token_hex
from typing import ParamSpec, TypeVar

from pymongo import ASCENDING, DESCENDING, ReturnDocument
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError, PyMongoError

from noteapp.application.ports.note_repository import NotePage
from noteapp.application.ports.reminder_repository import ClaimedReminder
from noteapp.domain.entities.category import Category
from noteapp.domain.entities.note import Note
from noteapp.domain.entities.reminder import ReminderStatus
from noteapp.domain.errors import (
    CategoryInUse,
    CategoryNotFound,
    DuplicateCategory,
    RepositoryUnavailable,
    ValidationError,
)
from noteapp.infrastructure.mongo.models import (
    attachment_to_document,
    category_from_document,
    category_to_document,
    decode_cursor,
    encode_cursor,
    note_from_document,
    note_to_document,
    object_id,
    reminder_to_document,
)

P = ParamSpec("P")
R = TypeVar("R")


def database_errors(method: Callable[P, R]) -> Callable[P, R]:
    @wraps(method)
    def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return method(*args, **kwargs)
        except PyMongoError:
            raise RepositoryUnavailable("Database operation was not acknowledged.") from None

    return wrapped


class MongoNoteRepository:
    def __init__(self, database: Database) -> None:
        self.collection = database.notes

    @database_errors
    def create(self, note: Note, operation_id: str) -> Note:
        document = note_to_document(note, operation_id)
        try:
            self.collection.insert_one(document)
        except DuplicateKeyError:
            existing = self.collection.find_one({"client_operation_id": operation_id})
            if existing is None:
                raise RepositoryUnavailable("Create could not be acknowledged.") from None
            return note_from_document(existing)
        # Return the actual persisted representation (BSON timestamp precision).
        persisted = self.collection.find_one({"_id": document["_id"]})
        if persisted is None:
            raise RepositoryUnavailable("Create could not be read back.")
        return note_from_document(persisted)

    @database_errors
    def find_by_id(self, note_id: str) -> Note | None:
        document = self.collection.find_one({"_id": object_id(note_id), "is_deleted": False})
        return note_from_document(document) if document is not None else None

    @database_errors
    def list_recent(self, limit: int, cursor: str | None = None) -> NotePage:
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValidationError("Page size must be between 1 and 100.")
        query = {"is_deleted": False}
        if cursor is not None:
            timestamp, note_id = decode_cursor(cursor)
            query["$or"] = [
                {"updated_at": {"$lt": timestamp}},
                {"updated_at": timestamp, "_id": {"$lt": note_id}},
            ]
        documents = list(
            self.collection.find(query)
            .sort([("updated_at", DESCENDING), ("_id", DESCENDING)])
            .limit(limit + 1)
        )
        items = tuple(note_from_document(document) for document in documents[:limit])
        return NotePage(items, encode_cursor(items[-1]) if len(documents) > limit else None)

    @database_errors
    def update_if_version(self, note: Note, expected_version: int) -> bool:
        if type(expected_version) is not int or expected_version < 1:
            raise ValidationError("Expected version must be a positive integer.")
        if note.version != expected_version + 1:
            raise ValidationError("Update must advance version by one.")
        result = self.collection.update_one(
            {"_id": object_id(note.id), "version": expected_version, "is_deleted": False},
            {
                "$set": {
                    "title": note.title,
                    "content_plain": note.content,
                    "priority": note.priority.value,
                    "priority_rank": note.priority.rank,
                    "category_id": object_id(note.category_id) if note.category_id else None,
                    "updated_at": note.updated_at,
                },
                "$inc": {"version": 1},
            },
        )
        return result.matched_count == 1


class MongoNoteAttachmentRepository:
    """CAS on the attachment field only; never rewrites text fields."""

    def __init__(self, database: Database) -> None:
        self.collection = database.notes

    @database_errors
    def set_attachment_if_version(self, note: Note, expected_version: int) -> bool:
        if type(expected_version) is not int or expected_version < 1:
            raise ValidationError("Expected version must be a positive integer.")
        if note.version != expected_version + 1:
            raise ValidationError("Update must advance version by one.")
        change = (
            {"$set": {"attachment": attachment_to_document(note.attachment)}}
            if note.attachment is not None
            else {"$unset": {"attachment": ""}}
        )
        change.setdefault("$set", {})["updated_at"] = note.updated_at
        result = self.collection.update_one(
            {"_id": object_id(note.id), "version": expected_version, "is_deleted": False},
            {**change, "$inc": {"version": 1}},
        )
        return result.matched_count == 1


class MongoReminderRepository:
    """Reminder state embedded in the note document.

    Configuration changes are CAS on the note version and replace the whole sub-document, which
    also discards any claim in flight (a reschedule or cancel always wins over an older claim).
    Delivery transitions (claim, delivered, release) do not touch version or updated_at, so an
    open editor is never made stale by a notification.
    """

    def __init__(self, database: Database) -> None:
        self.collection = database.notes

    @database_errors
    def set_reminder_if_version(self, note: Note, expected_version: int) -> bool:
        if type(expected_version) is not int or expected_version < 1:
            raise ValidationError("Expected version must be a positive integer.")
        if note.version != expected_version + 1:
            raise ValidationError("Update must advance version by one.")
        fields = {"updated_at": note.updated_at}
        change = (
            {"$set": {**fields, "reminder": reminder_to_document(note.reminder)}}
            if note.reminder is not None
            else {"$set": fields, "$unset": {"reminder": ""}}
        )
        guard = {"_id": object_id(note.id), "version": expected_version, "is_deleted": False}
        if note.reminder is not None and note.reminder.status is ReminderStatus.CANCELLED:
            guard["reminder.status"] = "ACTIVE"  # a delivery that already happened is kept
        result = self.collection.update_one(guard, {**change, "$inc": {"version": 1}})
        return result.matched_count == 1

    @database_errors
    def claim_next_due(
        self, now: datetime, lease_until: datetime, claim_token: str, max_attempts: int
    ) -> ClaimedReminder | None:
        if type(max_attempts) is not int or max_attempts < 1:
            raise ValidationError("Maximum attempts must be a positive integer.")
        document = self.collection.find_one_and_update(
            {
                "is_deleted": False,
                "reminder.status": "ACTIVE",
                "reminder.due_at": {"$lte": now},
                "reminder.attempts": {"$not": {"$gte": max_attempts}},
                "$and": [
                    {
                        "$or": [
                            {"reminder.claim_until": {"$exists": False}},
                            {"reminder.claim_until": {"$lte": now}},
                        ]
                    },
                    {
                        "$or": [
                            {"reminder.next_attempt_at": {"$exists": False}},
                            {"reminder.next_attempt_at": {"$lte": now}},
                        ]
                    },
                ],
            },
            {
                "$set": {
                    "reminder.claim_token": claim_token,
                    "reminder.claim_until": lease_until,
                },
                "$inc": {"reminder.attempts": 1},
                "$unset": {"reminder.next_attempt_at": ""},
            },
            sort=[("reminder.due_at", ASCENDING), ("_id", ASCENDING)],
            return_document=ReturnDocument.AFTER,
        )
        if document is None:
            return None
        reminder = document["reminder"]
        return ClaimedReminder(
            str(document["_id"]),
            document["title"],
            reminder["due_at"],
            claim_token,
            reminder["attempts"],
        )

    @database_errors
    def mark_delivered(self, note_id: str, claim_token: str, now: datetime) -> bool:
        result = self.collection.update_one(
            {
                "_id": object_id(note_id),
                "reminder.status": "ACTIVE",
                "reminder.claim_token": claim_token,
            },
            {
                "$set": {
                    "reminder.status": "DELIVERED",
                    "reminder.delivered_at": now,
                    "reminder.updated_at": now,
                },
                "$unset": {
                    "reminder.claim_token": "",
                    "reminder.claim_until": "",
                    "reminder.attempts": "",
                    "reminder.next_attempt_at": "",
                },
            },
        )
        return result.matched_count == 1

    @database_errors
    def release_claim(self, note_id: str, claim_token: str, retry_at: datetime) -> bool:
        result = self.collection.update_one(
            {
                "_id": object_id(note_id),
                "reminder.status": "ACTIVE",
                "reminder.claim_token": claim_token,
            },
            {
                "$set": {"reminder.next_attempt_at": retry_at},
                "$unset": {"reminder.claim_token": "", "reminder.claim_until": ""},
            },
        )
        return result.matched_count == 1


DELETE_MARKER_SECONDS = 30


class MongoCategoryRepository:
    """Category catalog. Uniqueness is enforced by the name_key unique index.

    Delete is mark -> count references -> conditional delete. The short-lived marker hides
    the category from lookups (so note writers stop accepting it) and expires by itself if
    the process dies between steps. There is no cross-collection transaction, so a note
    saved in the instant between a writer's lookup and insert can still dangle; readers
    already treat dangling references as uncategorized.
    """

    def __init__(self, database: Database) -> None:
        self.collection = database.categories
        self.notes = database.notes

    @staticmethod
    def _visible(now: datetime | None = None) -> dict:
        now = now if now is not None else datetime.now(timezone.utc)
        return {
            "$or": [
                {"deleting_until": {"$exists": False}},
                {"deleting_until": {"$lte": now}},
            ]
        }

    @database_errors
    def create(self, category: Category) -> Category:
        try:
            self.collection.insert_one(category_to_document(category))
        except DuplicateKeyError:
            raise DuplicateCategory("Category name already exists.") from None
        return category

    @database_errors
    def find_by_id(self, category_id: str) -> Category | None:
        document = self.collection.find_one({"_id": object_id(category_id), **self._visible()})
        return category_from_document(document) if document is not None else None

    @database_errors
    def list_all(self) -> tuple[Category, ...]:
        return tuple(
            category_from_document(document)
            for document in self.collection.find(self._visible()).sort("name_key", 1)
        )

    @database_errors
    def update(self, category: Category) -> Category:
        document = category_to_document(category)
        try:
            result = self.collection.update_one(
                {"_id": document["_id"], **self._visible()},
                {
                    "$set": {
                        "name": document["name"],
                        "name_key": document["name_key"],
                        "color_hex": document["color_hex"],
                    }
                },
            )
        except DuplicateKeyError:
            raise DuplicateCategory("Category name already exists.") from None
        if result.matched_count != 1:
            raise CategoryNotFound("Category not found.")
        persisted = self.find_by_id(category.id)
        if persisted is None:
            raise CategoryNotFound("Category not found.")
        return persisted

    @database_errors
    def count_notes_by_category(self, category_id: str) -> int:
        identifier = object_id(category_id)
        return sum(
            self.notes.count_documents({"is_deleted": deleted, "category_id": identifier})
            for deleted in (False, True)
        )

    @database_errors
    def delete(self, category_id: str) -> None:
        identifier = object_id(category_id)
        now = datetime.now(timezone.utc)
        token = token_hex(8)
        marked = self.collection.update_one(
            {"_id": identifier, **self._visible(now)},
            {
                "$set": {
                    "deleting_token": token,
                    "deleting_until": now + timedelta(seconds=DELETE_MARKER_SECONDS),
                }
            },
        )
        if marked.matched_count != 1:
            raise CategoryNotFound("Category not found.")
        try:
            in_use = self.count_notes_by_category(category_id) > 0
            if not in_use:
                result = self.collection.delete_one({"_id": identifier, "deleting_token": token})
                if result.deleted_count != 1:
                    raise CategoryNotFound("Category not found.")
                return
        except BaseException:
            self._release(identifier, token)
            raise
        self._release(identifier, token)
        raise CategoryInUse("Category is still referenced by notes.")

    def _release(self, identifier, token: str) -> None:
        try:
            self.collection.update_one(
                {"_id": identifier, "deleting_token": token},
                {"$unset": {"deleting_token": "", "deleting_until": ""}},
            )
        except PyMongoError:
            pass  # the marker expires on its own after DELETE_MARKER_SECONDS
