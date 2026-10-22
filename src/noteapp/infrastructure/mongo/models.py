"""Only this adapter boundary converts between opaque IDs and BSON."""

import base64
import json
from datetime import datetime, timezone
from typing import Any

from bson import ObjectId

from noteapp.domain.entities.category import Category
from noteapp.domain.entities.note import Note
from noteapp.domain.errors import ValidationError
from noteapp.domain.value_objects.attachment_ref import AttachmentRef


def object_id(value: str) -> ObjectId:
    if not isinstance(value, str) or not ObjectId.is_valid(value):
        raise ValidationError("Invalid record ID.")
    return ObjectId(value)


def note_to_document(note: Note, operation_id: str) -> dict[str, Any]:
    return {
        "_id": object_id(note.id),
        "client_operation_id": operation_id,
        "title": note.title,
        "content_plain": note.content,
        "priority": note.priority.value,
        "priority_rank": note.priority.rank,
        "category_id": object_id(note.category_id) if note.category_id is not None else None,
        "version": note.version,
        "created_at": note.created_at,
        "updated_at": note.updated_at,
        "is_deleted": False,
        "schema_version": 1,
    }


def attachment_to_document(ref: AttachmentRef) -> dict[str, Any]:
    return {
        "storage_kind": ref.storage_kind.value,
        "storage_key": ref.storage_key,
        "mime_type": ref.mime_type,
        "size_bytes": ref.size_bytes,
        "sha256": ref.sha256,
        "display_name": ref.display_name,
    }


def attachment_from_document(document: dict[str, Any] | None) -> AttachmentRef | None:
    if document is None:
        return None
    try:
        return AttachmentRef(
            document["storage_kind"],
            document["storage_key"],
            document["mime_type"],
            document["size_bytes"],
            document["sha256"],
            document["display_name"],
        )
    except (KeyError, TypeError):
        raise ValidationError("Stored attachment reference is malformed.") from None


def note_from_document(document: dict[str, Any]) -> Note:
    category_id = document.get("category_id")
    return Note(
        str(document["_id"]),
        document["title"],
        document["content_plain"],
        document["priority"],
        str(category_id) if category_id is not None else None,
        document["version"],
        document["created_at"],
        document["updated_at"],
        attachment_from_document(document.get("attachment")),
    )


def category_to_document(category: Category) -> dict[str, Any]:
    return {
        "_id": object_id(category.id),
        "name": category.name,
        "name_key": category.name_key,
        "color_hex": category.color_hex,
        "created_at": category.created_at,
    }


def category_from_document(document: dict[str, Any]) -> Category:
    return Category(
        str(document["_id"]), document["name"], document["color_hex"], document["created_at"]
    )


def encode_cursor(note: Note) -> str:
    # Mongo stores milliseconds: encode the timestamp read back from Mongo.
    payload = json.dumps([note.updated_at.isoformat(), note.id], separators=(",", ":"))
    return base64.urlsafe_b64encode(payload.encode()).decode()


def decode_cursor(cursor: str) -> tuple[datetime, ObjectId]:
    try:
        if not isinstance(cursor, str) or len(cursor) > 512:
            raise ValueError
        payload = json.loads(base64.b64decode(cursor, altchars=b"-_", validate=True))
        if not isinstance(payload, list) or len(payload) != 2:
            raise ValueError
        timestamp = datetime.fromisoformat(payload[0])
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError
        return timestamp.astimezone(timezone.utc), object_id(payload[1])
    except (ValueError, TypeError, KeyError, OverflowError):
        raise ValidationError("Invalid pagination cursor.") from None
