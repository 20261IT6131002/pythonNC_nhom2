"""Opaque key material in explicit native OS backends, without plugin/file fallback."""

import base64
import hmac
import re
import sys
from importlib import import_module

from keyring.backend import KeyringBackend

from noteapp.domain.errors import SecureStorageUnavailable, ValidationError

KEYRING_SERVICE = "noteapp.secure-storage.v1"
SECRET_PREFIX = "noteapp-key-v1:"
MAX_SECRET_BYTES = 512
SECRET_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")
UNAVAILABLE_MESSAGE = "Native secure storage is unavailable or did not acknowledge the operation."


def _validate_name(name: str) -> None:
    if not isinstance(name, str) or SECRET_NAME.fullmatch(name) is None:
        raise ValidationError("Secret name is invalid.")


def _validate_secret(secret: bytes) -> None:
    if type(secret) is not bytes or not 1 <= len(secret) <= MAX_SECRET_BYTES:
        raise ValidationError("Secret must contain 1–512 bytes.")


def _load_native_backend() -> KeyringBackend:
    if sys.platform == "win32":
        module_name, class_name = "keyring.backends.Windows", "WinVaultKeyring"
    elif sys.platform == "darwin":
        module_name, class_name = "keyring.backends.macOS", "Keyring"
    elif sys.platform.startswith("linux"):
        module_name, class_name = "keyring.backends.SecretService", "Keyring"
    else:
        raise SecureStorageUnavailable(UNAVAILABLE_MESSAGE)

    backend_type = getattr(import_module(module_name), class_name)
    backend = backend_type()

    if backend.priority <= 0:
        raise SecureStorageUnavailable(UNAVAILABLE_MESSAGE)

    if sys.platform == "win32":
        # Draft keys belong to this machine rather than roaming Windows profiles.
        backend.persist = "local machine"

    return backend


class KeyringSecretStore:
    """Creation does no OS I/O; get/put/delete must be called from workers."""

    def __init__(self) -> None:
        self._backend: KeyringBackend | None = None

    def _resolve(self) -> KeyringBackend:
        if self._backend is None:
            self._backend = _load_native_backend()

        return self._backend

    def get(self, name: str) -> bytes | None:
        _validate_name(name)

        try:
            encoded = self._resolve().get_password(KEYRING_SERVICE, name)

            if encoded is None:
                return None

            max_encoded_length = len(SECRET_PREFIX) + 4 * ((MAX_SECRET_BYTES + 2) // 3)

            if (
                not isinstance(encoded, str)
                or not encoded.startswith(SECRET_PREFIX)
                or len(encoded) > max_encoded_length
            ):
                raise ValueError("Stored key encoding is unsupported.")

            secret = base64.b64decode(
                encoded.removeprefix(SECRET_PREFIX).encode("ascii"), validate=True
            )
            _validate_secret(secret)

            return secret
        except Exception:
            raise SecureStorageUnavailable(UNAVAILABLE_MESSAGE) from None

    def put(self, name: str, secret: bytes) -> None:
        _validate_name(name)
        _validate_secret(secret)
        encoded = SECRET_PREFIX + base64.b64encode(secret).decode("ascii")

        try:
            backend = self._resolve()
            backend.set_password(KEYRING_SERVICE, name, encoded)
            acknowledged = backend.get_password(KEYRING_SERVICE, name)

            if not isinstance(acknowledged, str) or not hmac.compare_digest(acknowledged, encoded):
                raise ValueError("Native write was not acknowledged.")
        except Exception:
            raise SecureStorageUnavailable(UNAVAILABLE_MESSAGE) from None

    def delete(self, name: str) -> None:
        _validate_name(name)

        try:
            backend = self._resolve()

            if backend.get_password(KEYRING_SERVICE, name) is None:
                return

            backend.delete_password(KEYRING_SERVICE, name)

            if backend.get_password(KEYRING_SERVICE, name) is not None:
                raise ValueError("Native deletion was not acknowledged.")
        except Exception:
            raise SecureStorageUnavailable(UNAVAILABLE_MESSAGE) from None
