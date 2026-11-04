"""R1-02: safe envelope fields and strict typed error/result contracts."""

from dataclasses import FrozenInstanceError, replace

import pytest

from noteapp.application.dto.encrypted_envelope import EncryptedEnvelope
from noteapp.application.dto.operation_result import ErrorCode, OperationResult
from noteapp.domain.errors import AuthenticationFailed, SecureStorageUnavailable, ValidationError


def envelope():
    return EncryptedEnvelope(1, "AES-256-GCM", b"nonce-marker", b"ciphertext-marker-with-tag")


def test_envelope_is_immutable_and_omits_sensitive_bytes_from_repr():
    value = envelope()

    assert "nonce-marker" not in repr(value)
    assert "ciphertext-marker" not in repr(value)
    assert value.nonce == b"nonce-marker"

    with pytest.raises(FrozenInstanceError):
        value.format_version = 2


@pytest.mark.parametrize(
    "field,value",
    [
        ("format_version", True),
        ("format_version", 0),
        ("format_version", 2),
        ("format_version", "1"),
        ("algorithm", "AES-128-GCM"),
        ("algorithm", None),
        ("nonce", b""),
        ("nonce", b"x" * 11),
        ("nonce", b"x" * 13),
        ("nonce", "x" * 12),
        ("nonce", bytearray(12)),
        ("ciphertext", b""),
        ("ciphertext", b"x" * 15),
        ("ciphertext", "x" * 16),
        ("ciphertext", bytearray(16)),
    ],
)
def test_malformed_envelopes_are_rejected_without_echoing_payloads(field, value):
    with pytest.raises(ValidationError) as raised:
        replace(envelope(), **{field: value})

    assert "nonce-marker" not in str(raised.value)
    assert "ciphertext-marker" not in str(raised.value)


@pytest.mark.parametrize(
    "error,code",
    [
        (AuthenticationFailed("sensitive provider details"), ErrorCode.AUTHENTICATION_FAILED),
        (
            SecureStorageUnavailable("sensitive provider details"),
            ErrorCode.SECURE_STORAGE_UNAVAILABLE,
        ),
    ],
)
def test_security_errors_cross_worker_boundary_as_codes_only(error, code):
    result = OperationResult.failed(error)

    assert result.error == code
    assert result.value is None
    assert not result.ok
    assert "sensitive provider details" not in repr(result)


def test_worker_result_repr_does_not_expose_decrypted_bytes():
    plaintext = b"private-decrypted-worker-value"
    result = OperationResult(value=plaintext)

    assert result.ok and result.value == plaintext
    assert "private-decrypted-worker-value" not in repr(result)
