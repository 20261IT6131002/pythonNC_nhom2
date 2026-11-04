"""Test-only secret and native-backend doubles; never used by runtime composition."""

import re

from noteapp.domain.errors import SecureStorageUnavailable, ValidationError


class FakeSecretStore:
    def __init__(self) -> None:
        self._items: dict[str, bytes] = {}
        self.available = True

    def _validate(self, name: str) -> None:
        if (
            not isinstance(name, str)
            or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", name) is None
        ):
            raise ValidationError("Secret name is invalid.")

        if not self.available:
            raise SecureStorageUnavailable("Native secure storage is unavailable.")

    def get(self, name: str) -> bytes | None:
        self._validate(name)
        return self._items.get(name)

    def put(self, name: str, secret: bytes) -> None:
        self._validate(name)

        if type(secret) is not bytes or not 1 <= len(secret) <= 512:
            raise ValidationError("Secret must contain 1–512 bytes.")

        self._items[name] = secret

    def delete(self, name: str) -> None:
        self._validate(name)
        self._items.pop(name, None)


class MemoryNativeBackend:
    """Native API test double; production does not accept this as a backend option."""

    priority = 1

    def __init__(self) -> None:
        self.values: dict[tuple[str, str], str] = {}
        self.error: Exception | None = None
        self.write_acknowledged = True
        self.delete_acknowledged = True

    def _check(self) -> None:
        if self.error is not None:
            raise self.error

    def get_password(self, service: str, username: str) -> str | None:
        self._check()
        return self.values.get((service, username))

    def set_password(self, service: str, username: str, password: str) -> None:
        self._check()

        if self.write_acknowledged:
            self.values[service, username] = password

    def delete_password(self, service: str, username: str) -> None:
        self._check()

        if self.delete_acknowledged:
            self.values.pop((service, username), None)
