"""Strict envelope transport never accepts unknown fields or serializes plaintext/keys."""

import base64
import json

import pytest

from noteapp.domain.errors import ValidationError
from noteapp.infrastructure.security.aes_gcm import AesGcmCipher
from noteapp.infrastructure.security.serializers import decode_envelope, encode_envelope


def test_envelope_transport_roundtrip_contains_only_encrypted_bytes():
    key, aad = bytes(range(32)), b"test:storage:record-1"
    plaintext = b"plaintext-never-in-envelope-json"
    envelope = AesGcmCipher().encrypt(plaintext, key, aad)
    encoded = encode_envelope(envelope)

    assert plaintext not in encoded
    assert base64.b64encode(key) not in encoded
    assert set(json.loads(encoded)) == {"format_version", "algorithm", "nonce", "ciphertext"}
    assert decode_envelope(encoded) == envelope
    assert AesGcmCipher().decrypt(decode_envelope(encoded), key, aad) == plaintext


@pytest.mark.parametrize(
    "payload",
    [
        b"not-json",
        b"null",
        b"[]",
        b"{}",
        b"\xff",
        "{}",
        None,
        b'{"format_version":1,"format_version":1}',
    ],
)
def test_invalid_transport_fails_without_payload_in_error(payload):
    with pytest.raises(ValidationError) as raised:
        decode_envelope(payload)

    assert str(raised.value) == "Encrypted envelope is malformed or unsupported."


@pytest.mark.parametrize(
    "field,value",
    [
        ("format_version", 2),
        ("format_version", True),
        ("algorithm", "AES-128-GCM"),
        ("nonce", "!invalid-base64!"),
        ("nonce", "AA=="),
        ("nonce", None),
        ("ciphertext", "AA=="),
        ("ciphertext", "秘密"),
        ("plaintext", "private-marker"),
    ],
)
def test_invalid_or_extra_fields_are_rejected(field, value):
    envelope = AesGcmCipher().encrypt(b"content", bytes(range(32)), b"context")
    document = json.loads(encode_envelope(envelope))
    document[field] = value

    with pytest.raises(ValidationError):
        decode_envelope(json.dumps(document).encode())


def test_duplicate_field_in_an_otherwise_valid_envelope_is_rejected():
    envelope = AesGcmCipher().encrypt(b"content", bytes(range(32)), b"context")
    encoded = encode_envelope(envelope)
    duplicated = encoded[:-1] + b',"format_version":1}'

    with pytest.raises(ValidationError):
        decode_envelope(duplicated)
