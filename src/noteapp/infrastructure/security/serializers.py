"""Strict JSON/base64 transport for encrypted envelopes, with no plaintext or file I/O."""

import base64
import json
from typing import Any

from noteapp.application.dto.encrypted_envelope import EncryptedEnvelope
from noteapp.domain.errors import ValidationError

ENVELOPE_FIELDS = {"format_version", "algorithm", "nonce", "ciphertext"}


def _unique_fields(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}

    for name, value in pairs:
        if name in result:
            raise ValueError("Duplicate envelope field.")

        result[name] = value

    return result


def _decode_bytes(value: str) -> bytes:
    if not isinstance(value, str):
        raise ValueError("Envelope byte field must be base64 text.")

    return base64.b64decode(value.encode("ascii"), validate=True)


def encode_envelope(envelope: EncryptedEnvelope) -> bytes:
    if not isinstance(envelope, EncryptedEnvelope):
        raise ValidationError("A typed encrypted envelope is required.")

    document = {
        "format_version": envelope.format_version,
        "algorithm": envelope.algorithm,
        "nonce": base64.b64encode(envelope.nonce).decode("ascii"),
        "ciphertext": base64.b64encode(envelope.ciphertext).decode("ascii"),
    }

    return json.dumps(document, separators=(",", ":"), sort_keys=True).encode("utf-8")


def decode_envelope(payload: bytes) -> EncryptedEnvelope:
    try:
        if type(payload) is not bytes:
            raise ValueError("Envelope transport must be bytes.")

        document = json.loads(payload.decode("utf-8"), object_pairs_hook=_unique_fields)

        if not isinstance(document, dict) or set(document) != ENVELOPE_FIELDS:
            raise ValueError("Envelope field set does not match.")

        return EncryptedEnvelope(
            format_version=document["format_version"],
            algorithm=document["algorithm"],
            nonce=_decode_bytes(document["nonce"]),
            ciphertext=_decode_bytes(document["ciphertext"]),
        )
    except (ValueError, TypeError, UnicodeError, RecursionError, ValidationError):
        raise ValidationError("Encrypted envelope is malformed or unsupported.") from None
