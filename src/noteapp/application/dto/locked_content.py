"""Versioned passphrase-encrypted note payload."""

from dataclasses import dataclass, field

from noteapp.application.dto.encrypted_envelope import EncryptedEnvelope
from noteapp.domain.errors import ValidationError

KDF_NAME = "PBKDF2-HMAC-SHA256"
KDF_ITERATIONS = 600_000
SALT_BYTES = 16
MAX_CONTENT_BYTES = 1024 * 1024
# JSON may encode control characters as six bytes each.
MAX_CIPHERTEXT_BYTES = 6 * MAX_CONTENT_BYTES + 8192


@dataclass(frozen=True)
class LockedContent:
    salt: bytes = field(repr=False)
    envelope: EncryptedEnvelope = field(repr=False)

    def __post_init__(self) -> None:
        if type(self.salt) is not bytes or len(self.salt) != SALT_BYTES:
            raise ValidationError("Invalid encrypted note salt.")
        if not isinstance(self.envelope, EncryptedEnvelope):
            raise ValidationError("Invalid encrypted note envelope.")
        if len(self.envelope.ciphertext) > MAX_CIPHERTEXT_BYTES:
            raise ValidationError("Encrypted note exceeds the supported size.")
