"""FR-10: deliver due reminders once per claim, best effort.

Flow per reminder: atomic claim -> OS notification -> mark delivered. A failed notification
releases the claim with a retry delay; after MAX_DELIVERY_ATTEMPTS the reminder stays ACTIVE
but is no longer polled (the user can reschedule it). Delivery is at-least-once-ish and not
exactly-once: a crash between notify and mark_delivered re-notifies after the lease expires.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from secrets import token_hex

from noteapp.application.ports.clock import Clock
from noteapp.application.ports.notification_gateway import NotificationGateway
from noteapp.application.ports.reminder_repository import ReminderRepository
from noteapp.domain.errors import NoteAppError
from noteapp.domain.policies.reminder_policy import (
    CLAIM_LEASE,
    MAX_DELIVERY_ATTEMPTS,
    NOTIFICATION_TITLE_MAX,
    retry_delay,
)

LOGGER = logging.getLogger("noteapp.reminders")
NOTIFICATION_TITLE = "Nhắc nhở"


@dataclass(frozen=True)
class DeliveredReminder:
    note_id: str
    delivered_at: datetime


@dataclass(frozen=True)
class DeliveryReport:
    delivered: tuple[DeliveredReminder, ...] = ()
    failed_note_ids: tuple[str, ...] = ()
    unavailable: bool = False

    @property
    def failed(self) -> int:
        return len(self.failed_note_ids)

    @property
    def noteworthy(self) -> bool:
        """Whether the UI has anything to show: a delivery or a failed attempt."""
        return bool(self.delivered or self.failed_note_ids)


def notification_message(title: str) -> str:
    text = " ".join(title.split())
    if len(text) > NOTIFICATION_TITLE_MAX:
        text = text[: NOTIFICATION_TITLE_MAX - 1] + "…"
    return text


class ReminderDeliveryService:
    def __init__(
        self,
        reminders: ReminderRepository,
        gateway: NotificationGateway,
        clock: Clock,
        batch_size: int = 20,
    ) -> None:
        self.reminders, self.gateway, self.clock = reminders, gateway, clock
        self.batch_size = batch_size

    def deliver_due(self, should_continue: Callable[[], bool] = lambda: True) -> DeliveryReport:
        """Claim and deliver up to batch_size due reminders; never raises for expected faults."""
        delivered: list[DeliveredReminder] = []
        failed: list[str] = []
        for _ in range(self.batch_size):
            if not should_continue():
                break
            now = self.clock.now()
            try:
                claimed = self.reminders.claim_next_due(
                    now, now + CLAIM_LEASE, token_hex(16), MAX_DELIVERY_ATTEMPTS
                )
            except NoteAppError:
                LOGGER.warning("reminder_claim_unavailable")
                return DeliveryReport(tuple(delivered), tuple(failed), unavailable=True)
            if claimed is None:
                break
            try:
                self.gateway.notify(NOTIFICATION_TITLE, notification_message(claimed.title))
            except Exception:  # sanitized: provider errors may carry paths or internals
                failed.append(claimed.note_id)
                LOGGER.warning("reminder_notification_failed", extra={"stage": "notify"})
                self._release(claimed.note_id, claimed.claim_token, claimed.attempts)
                continue
            done = self.clock.now()
            try:
                if self.reminders.mark_delivered(claimed.note_id, claimed.claim_token, done):
                    delivered.append(DeliveredReminder(claimed.note_id, done))
            except NoteAppError:
                LOGGER.warning("reminder_mark_unconfirmed", extra={"stage": "mark_delivered"})
                return DeliveryReport(tuple(delivered), tuple(failed), unavailable=True)
        return DeliveryReport(tuple(delivered), tuple(failed))

    def _release(self, note_id: str, token: str, attempts: int) -> None:
        try:
            self.reminders.release_claim(note_id, token, self.clock.now() + retry_delay(attempts))
        except NoteAppError:
            LOGGER.warning("reminder_release_unavailable", extra={"stage": "release"})
