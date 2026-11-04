"""Immutable, library-independent envelope for authenticated encrypted bytes."""

from dataclasses import dataclass, field

from noteapp.domain.errors import ValidationError

ENVELOPE_VERSION = 1
ENVELOPE_ALGORITHM = "AES-256-GCM"
NONCE_BYTES = 12
TAG_BYTES = 16


@dataclass(frozen=True)
class EncryptedEnvelope:
    format_version: int
    algorithm: str
    nonce: bytes = field(repr=False)
    ciphertext: bytes = field(repr=False)

    def __post_init__(self) -> None:
        if type(self.format_version) is not int or self.format_version != ENVELOPE_VERSION:
            raise ValidationError("Unsupported encrypted envelope version.")

        if self.algorithm != ENVELOPE_ALGORITHM:
            raise ValidationError("Unsupported encrypted envelope algorithm.")

        if type(self.nonce) is not bytes or len(self.nonce) != NONCE_BYTES:
            raise ValidationError("Encrypted envelope requires a 12-byte nonce.")

        if type(self.ciphertext) is not bytes or len(self.ciphertext) < TAG_BYTES:
            raise ValidationError("Encrypted envelope requires a complete authentication tag.")
