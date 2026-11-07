from hashlib import pbkdf2_hmac

from noteapp.application.dto.locked_content import KDF_ITERATIONS


class Pbkdf2PassphraseKdf:
    def derive(self, passphrase: bytes, salt: bytes) -> bytes:
        return pbkdf2_hmac("sha256", passphrase, salt, KDF_ITERATIONS, dklen=32)
