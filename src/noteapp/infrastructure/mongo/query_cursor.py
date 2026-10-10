"""Opaque, versioned query-bound seek cursors; never accept query fragments."""

import base64
import hashlib
import json
from dataclasses import asdict
from datetime import datetime
from typing import Any

from noteapp.domain.errors import ValidationError


def fingerprint(criteria: Any) -> str:
    values = asdict(criteria) if hasattr(criteria, "__dataclass_fields__") else dict(criteria)
    values.pop("cursor", None)
    payload = json.dumps(
        values,
        default=lambda item: item.isoformat() if isinstance(item, datetime) else item.value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def encode_seek(namespace: str, signature: str, keys: list[Any], note_id: str) -> str:
    payload = {"v": 1, "ns": namespace, "q": signature, "keys": keys, "id": note_id}
    result = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode()
    ).decode()
    if len(result) > 2048:
        raise ValidationError("Seek key exceeds cursor bounds.")
    return result


def decode_seek(cursor: str, namespace: str, signature: str) -> tuple[list[Any], str]:
    try:
        if not isinstance(cursor, str) or not cursor or len(cursor) > 2048:
            raise ValueError
        payload = json.loads(base64.b64decode(cursor, altchars=b"-_", validate=True))
        if not isinstance(payload, dict) or set(payload) != {"v", "ns", "q", "keys", "id"}:
            raise ValueError
        if (
            type(payload["v"]) is not int
            or payload["v"] != 1
            or payload["ns"] != namespace
            or payload["q"] != signature
        ):
            raise ValueError
        if not isinstance(payload["keys"], list) or not isinstance(payload["id"], str):
            raise ValueError
        return payload["keys"], payload["id"]
    except (ValueError, TypeError, UnicodeError, OverflowError):
        raise ValidationError("Invalid cursor for this query.") from None
