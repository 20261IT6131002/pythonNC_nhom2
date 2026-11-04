"""AES-256-GCM with fresh OS randomness and authenticated version/consumer context."""

from secrets import token_bytes

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from noteapp.application.dto.encrypted_envelope import (
    ENVELOPE_ALGORITHM,
    ENVELOPE_VERSION,
    NONCE_BYTES,
    EncryptedEnvelope,
)
from noteapp.domain.errors import AuthenticationFailed, SecureStorageUnavailable, ValidationError

AUTHENTICATED_CONTEXT = b"noteapp:envelope:v1:AES-256-GCM\x00"
KEY_BYTES = 32


def _validate_key_and_context(key: bytes, aad: bytes) -> None:
    if type(key) is not bytes or len(key) != KEY_BYTES:
        raise ValidationError("AES-256-GCM requires a 32-byte key.")

    if type(aad) is not bytes or not aad:
        raise ValidationError("Authenticated context must be nonempty bytes.")


class AesGcmCipher:
    """Stateless adapter: caller-owned keys are never cached or serialized."""

    def encrypt(self, plaintext: bytes, key: bytes, aad: bytes) -> EncryptedEnvelope:
        _validate_key_and_context(key, aad)

        if type(plaintext) is not bytes:
            raise ValidationError("Plaintext must be bytes.")

        try:
            nonce = token_bytes(NONCE_BYTES)
            ciphertext = AESGCM(key).encrypt(nonce, plaintext, AUTHENTICATED_CONTEXT + aad)
        except Exception:
            raise SecureStorageUnavailable("Authenticated encryption is unavailable.") from None

        return EncryptedEnvelope(ENVELOPE_VERSION, ENVELOPE_ALGORITHM, nonce, ciphertext)

    def decrypt(self, envelope: EncryptedEnvelope, key: bytes, aad: bytes) -> bytes:
        _validate_key_and_context(key, aad)

        if not isinstance(envelope, EncryptedEnvelope):
            raise ValidationError("A typed encrypted envelope is required.")

        try:
            return AESGCM(key).decrypt(
                envelope.nonce, envelope.ciphertext, AUTHENTICATED_CONTEXT + aad
            )
        except InvalidTag:
            raise AuthenticationFailed("Encrypted data could not be authenticated.") from None
        except Exception:
            raise SecureStorageUnavailable("Authenticated decryption is unavailable.") from None
