"""AEAD boundary; implementations own nonce generation and authenticate before returning."""

from typing import Protocol, runtime_checkable

from noteapp.application.dto.encrypted_envelope import EncryptedEnvelope


@runtime_checkable
class ContentCipher(Protocol):
    def encrypt(self, plaintext: bytes, key: bytes, aad: bytes) -> EncryptedEnvelope:
        """Encrypt with a 32-byte key, fresh nonce and nonempty context bytes."""

    def decrypt(self, envelope: EncryptedEnvelope, key: bytes, aad: bytes) -> bytes:
        """Authenticate the entire envelope/context, or raise without returning plaintext."""
