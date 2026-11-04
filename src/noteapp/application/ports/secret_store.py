"""Native secure-store contract; failures never imply a missing secret or plaintext fallback."""

from typing import Protocol, runtime_checkable


@runtime_checkable
class SecretStore(Protocol):
    def get(self, name: str) -> bytes | None:
        """Return a stored secret, or None only for a successful read of a missing name."""

    def put(self, name: str, secret: bytes) -> None:
        """Store 1–512 key-material bytes under an opaque name; verify acknowledgement."""

    def delete(self, name: str) -> None:
        """Delete an entry; a successfully verified absent entry is an idempotent no-op."""
