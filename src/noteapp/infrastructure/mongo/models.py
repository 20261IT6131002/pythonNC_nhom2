"""Only this adapter boundary converts between opaque IDs and BSON."""

import base64
import json
from datetime import datetime, timezone
from typing import Any

from bson import ObjectId

from noteapp.application.dto.encrypted_envelope import EncryptedEnvelope
from noteapp.application.dto.locked_content import KDF_ITERATIONS, KDF_NAME, LockedContent
from noteapp.domain.entities.category import Category
from noteapp.domain.entities.note import LOCKED_TITLE, LockedNote, Note
from noteapp.domain.entities.reminder import Reminder
from noteapp.domain.errors import ValidationError
from noteapp.domain.value_objects.attachment_ref import AttachmentRef


def object_id(value: str) -> ObjectId:
    if not isinstance(value, str) or not ObjectId.is_valid(value):
        raise ValidationError("Invalid record ID.")
    return ObjectId(value)


def note_to_document(note: Note, operation_id: str) -> dict[str, Any]:
    if note.is_locked:
        raise ValidationError("Locked metadata cannot be written as plaintext.")
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
        "is_pinned": note.is_pinned,
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


def reminder_to_document(reminder: Reminder) -> dict[str, Any]:
    document: dict[str, Any] = {
        "due_at": reminder.due_at,
        "status": reminder.status.value,
        "updated_at": reminder.updated_at,
    }
    if reminder.delivered_at is not None:
        document["delivered_at"] = reminder.delivered_at
    return document


def reminder_from_document(document: dict[str, Any] | None) -> Reminder | None:
    """Claim, lease and attempt counters are adapter-internal and not part of the entity."""
    if document is None:
        return None
    try:
        return Reminder(
            document["due_at"],
            document["status"],
            document["updated_at"],
            document.get("delivered_at"),
        )
    except (KeyError, TypeError):
        raise ValidationError("Stored reminder is malformed.") from None


def locked_to_document(payload: LockedContent) -> dict[str, Any]:
    return {
        "kdf": {"name": KDF_NAME, "iterations": KDF_ITERATIONS, "salt": payload.salt},
        "format_version": payload.envelope.format_version,
        "algorithm": payload.envelope.algorithm,
        "nonce": payload.envelope.nonce,
        "ciphertext": payload.envelope.ciphertext,
    }


def locked_from_document(document: dict[str, Any]) -> LockedContent:
    try:
        value = document["content_encrypted"]
        if set(value) != {"kdf", "format_version", "algorithm", "nonce", "ciphertext"}:
            raise ValueError
        kdf = value["kdf"]
        if (
            set(kdf) != {"name", "iterations", "salt"}
            or kdf["name"] != KDF_NAME
            or type(kdf["iterations"]) is not int
            or kdf["iterations"] != KDF_ITERATIONS
        ):
            raise ValueError
        return LockedContent(
            kdf["salt"],
            EncryptedEnvelope(
                value["format_version"], value["algorithm"], value["nonce"], value["ciphertext"]
            ),
        )
    except (KeyError, TypeError, ValueError, ValidationError):
        raise ValidationError("Stored encrypted note is malformed.") from None


def note_from_document(document: dict[str, Any]) -> Note:
    schema = document.get("schema_version")
    locked = document.get("is_locked", False)
    if type(schema) is not int or schema not in (1, 2, 3) or type(locked) is not bool:
        raise ValidationError("Unsupported stored note schema.")
    category_id = document.get("category_id")
    fields = dict(
        id=str(document["_id"]),
        priority=document["priority"],
        category_id=str(category_id) if category_id is not None else None,
        version=document["version"],
        created_at=document["created_at"],
        updated_at=document["updated_at"],
        attachment=attachment_from_document(document.get("attachment")),
        reminder=reminder_from_document(document.get("reminder")),
        is_pinned=document.get("is_pinned", False),
    )
    if locked:
        if schema != 3 or "content_plain" in document or document.get("title") != LOCKED_TITLE:
            raise ValidationError("Invalid locked note representation.")
        locked_from_document(document)
        return LockedNote(**fields)
    if (
        "content_encrypted" in document
        or not isinstance(document.get("content_plain"), str)
        or (schema == 3 and document.get("is_locked") is not False)
    ):
        raise ValidationError("Invalid plaintext note representation.")
    return Note(title=document["title"], content=document["content_plain"], **fields)


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
    payload = json.dumps([2, note.is_pinned, note.updated_at.isoformat(), note.id])
    return base64.urlsafe_b64encode(payload.encode()).decode()


def decode_cursor(cursor: str) -> tuple[bool, datetime, ObjectId]:
    try:
        if not isinstance(cursor, str) or len(cursor) > 512:
            raise ValueError
        payload = json.loads(base64.b64decode(cursor, altchars=b"-_", validate=True))
        if not isinstance(payload, list) or len(payload) != 4:
            raise ValueError
        if type(payload[0]) is not int or payload[0] != 2 or type(payload[1]) is not bool:
            raise ValueError
        timestamp = datetime.fromisoformat(payload[2])
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError
        return payload[1], timestamp.astimezone(timezone.utc), object_id(payload[3])
    except (ValueError, TypeError, KeyError, OverflowError):
        raise ValidationError("Invalid pagination cursor.") from None
