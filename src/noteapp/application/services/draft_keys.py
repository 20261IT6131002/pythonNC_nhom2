"""Draft-specific key lifecycle, separate from the generic OS SecretStore."""

import hmac
from collections.abc import Callable
from threading import Lock

from noteapp.application.ports.secret_store import SecretStore
from noteapp.domain.errors import SecureStorageUnavailable


class DraftKeyProvider:
    _provision_lock = Lock()

    def __init__(
        self, secrets: SecretStore, new_key: Callable[[], bytes], name: str = "draft-master-key.v1"
    ) -> None:
        self.secrets = secrets
        self.new_key = new_key
        self.name = name

    def get_key(self, *, existing_ciphertext: bool) -> bytes:
        try:
            return self._get_key(existing_ciphertext=existing_ciphertext)
        except SecureStorageUnavailable:
            raise
        except Exception:
            raise SecureStorageUnavailable("Draft key provisioning is unavailable.") from None

    def _get_key(self, *, existing_ciphertext: bool) -> bytes:
        with self._provision_lock:
            key = self.secrets.get(self.name)

            if key is None:
                if existing_ciphertext:
                    raise SecureStorageUnavailable(
                        "The existing draft encryption key is unavailable."
                    )

                key = self.new_key()

                if type(key) is not bytes or len(key) != 32:
                    raise SecureStorageUnavailable("Draft encryption key generation failed.")

                self.secrets.put(self.name, key)
                acknowledged = self.secrets.get(self.name)

                if type(acknowledged) is not bytes or not hmac.compare_digest(key, acknowledged):
                    raise SecureStorageUnavailable("Draft encryption key was not acknowledged.")

            if type(key) is not bytes or len(key) != 32:
                raise SecureStorageUnavailable("The stored draft encryption key is invalid.")

            return key
