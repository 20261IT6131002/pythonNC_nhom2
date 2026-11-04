"""Strict bounded payload/wrapper encoding. Only encrypted wrappers may reach disk."""

import json
from dataclasses import asdict
from datetime import datetime
from typing import Any

from noteapp.application.dto.encrypted_envelope import EncryptedEnvelope
from noteapp.application.dto.local_draft import (
    MAX_DRAFT_PAYLOAD_BYTES,
    LocalDraft,
    validate_draft_id,
)
from noteapp.domain.errors import ValidationError
from noteapp.infrastructure.security.serializers import decode_envelope, encode_envelope

PAYLOAD_FIELDS = {
    "draft_id",
    "note_id",
    "client_operation_id",
    "base_version",
    "revision",
    "title",
    "content",
    "priority",
    "category_id",
    "updated_at",
    "source_locked",
}
MAX_DRAFT_FILE_BYTES = 2 * 1024 * 1024


def _unique_fields(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    document = {}

    for name, value in pairs:
        if name in document:
            raise ValueError("Duplicate draft field.")

        document[name] = value

    return document


def _json_bytes(document: dict) -> bytes:
    return json.dumps(document, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _document(payload: bytes, fields: set[str], bound: int) -> dict:
    try:
        if type(payload) is not bytes or len(payload) > bound:
            raise ValueError

        document = json.loads(payload.decode("utf-8"), object_pairs_hook=_unique_fields)

        if not isinstance(document, dict) or set(document) != fields:
            raise ValueError

        return document
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise ValidationError("Draft data is malformed or exceeds the secure bound.") from None


def encode_draft_payload(draft: LocalDraft) -> bytes:
    document = asdict(draft)
    document["priority"] = draft.priority.value
    document["updated_at"] = draft.updated_at.isoformat()

    try:
        payload = _json_bytes(document)
    except (ValueError, TypeError, UnicodeError):
        raise ValidationError("Draft data could not be serialized safely.") from None

    if len(payload) > MAX_DRAFT_PAYLOAD_BYTES:
        raise ValidationError("Encrypted draft payload exceeds 1 MiB.")

    return payload


def decode_draft_payload(payload: bytes) -> LocalDraft:
    try:
        document = _document(payload, PAYLOAD_FIELDS, MAX_DRAFT_PAYLOAD_BYTES)
        document["updated_at"] = datetime.fromisoformat(document["updated_at"])
        return LocalDraft(**document)
    except (ValueError, TypeError, UnicodeError, ValidationError):
        raise ValidationError("Draft payload is malformed or unsupported.") from None


def encode_draft_wrapper(draft_id: str, envelope: EncryptedEnvelope) -> bytes:
    return _json_bytes(
        {
            "format_version": 1,
            "draft_id": validate_draft_id(draft_id),
            "encrypted_envelope": json.loads(encode_envelope(envelope)),
        }
    )


def decode_draft_wrapper(payload: bytes, draft_id: str) -> EncryptedEnvelope:
    document = _document(
        payload, {"format_version", "draft_id", "encrypted_envelope"}, MAX_DRAFT_FILE_BYTES
    )

    if type(document["format_version"]) is not int or document["format_version"] != 1:
        raise ValidationError("Unsupported draft format.")

    if validate_draft_id(document["draft_id"]) != validate_draft_id(draft_id):
        raise ValidationError("Draft wrapper identity does not match.")

    return decode_envelope(_json_bytes(document["encrypted_envelope"]))
