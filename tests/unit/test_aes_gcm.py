"""Provider failures are normalized and sensitive inputs never enter repr or logs."""

import traceback

import pytest

from noteapp.domain.errors import SecureStorageUnavailable, ValidationError
from noteapp.infrastructure.security import aes_gcm


def test_unsupported_crypto_provider_is_safe(monkeypatch, caplog):
    marker = "secret-provider-marker"

    def unavailable(*_args):
        raise RuntimeError(marker)

    monkeypatch.setattr(aes_gcm, "AESGCM", unavailable)

    with pytest.raises(SecureStorageUnavailable) as raised:
        aes_gcm.AesGcmCipher().encrypt(marker.encode(), bytes(range(32)), b"context")

    assert marker not in repr(raised.value)
    assert marker not in "".join(traceback.format_exception(raised.value))
    assert marker not in caplog.text
    assert raised.value.__cause__ is None


def test_random_source_failure_cannot_fall_back_to_a_fixed_nonce(monkeypatch):
    def unavailable(_size):
        raise OSError("random source unavailable")

    monkeypatch.setattr(aes_gcm, "token_bytes", unavailable)

    with pytest.raises(SecureStorageUnavailable):
        aes_gcm.AesGcmCipher().encrypt(b"content", bytes(range(32)), b"context")


@pytest.mark.parametrize("payload", ["plaintext", None, bytearray(b"plaintext")])
def test_encrypt_rejects_non_byte_plaintext(payload):
    with pytest.raises(ValidationError):
        aes_gcm.AesGcmCipher().encrypt(payload, bytes(range(32)), b"context")


def test_decrypt_rejects_untyped_envelopes():
    with pytest.raises(ValidationError):
        aes_gcm.AesGcmCipher().decrypt({"ciphertext": b"not-an-envelope"}, bytes(32), b"context")
