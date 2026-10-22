"""Operating-system notification port; carries plain text only."""

from typing import Protocol, runtime_checkable


@runtime_checkable
class NotificationGateway(Protocol):
    def notify(self, title: str, message: str) -> None:
        """Ask the OS to show a notification; raise NotificationFailure if it is not accepted."""
