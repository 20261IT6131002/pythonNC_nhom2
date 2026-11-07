from typing import Protocol


class PassphraseKdf(Protocol):
    def derive(self, passphrase: bytes, salt: bytes) -> bytes:
        """Derive a 32-byte note key using the locked content v1 KDF profile."""
