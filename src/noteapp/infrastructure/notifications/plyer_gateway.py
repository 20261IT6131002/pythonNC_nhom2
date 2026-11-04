"""OS notification through plyer. Plain text in; no database or domain objects."""

import logging

from noteapp.domain.errors import NotificationFailure

LOGGER = logging.getLogger("noteapp.reminders")
APP_NAME = "NoteApp"
DISPLAY_SECONDS = 10


class PlyerGateway:
    """Acceptance by plyer means the call returned; the OS may still hide the toast."""

    def __init__(self, notifier=None) -> None:
        self._notifier = notifier

    def _resolve(self):
        if self._notifier is None:
            from plyer import notification  # lazy: plyer import fails on unsupported desktops

            self._notifier = notification
        return self._notifier

    def notify(self, title: str, message: str) -> None:
        try:
            self._resolve().notify(
                title=title, message=message, app_name=APP_NAME, timeout=DISPLAY_SECONDS
            )
        except Exception:
            # Provider exceptions can include paths or backend details: log only a marker.
            LOGGER.warning("os_notification_rejected", extra={"stage": "plyer"})
            raise NotificationFailure(
                "The operating system did not accept the notification."
            ) from None
