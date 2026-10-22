"""Reminder value with an explicit three-state lifecycle (no I/O, no clock access)."""

from dataclasses import dataclass, replace
from datetime import datetime
from enum import Enum

from noteapp.domain.errors import ValidationError
from noteapp.domain.policies.note_validation import utc_datetime


class ReminderStatus(str, Enum):
    ACTIVE = "ACTIVE"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"


@dataclass(frozen=True)
class Reminder:
    """When to remind. DELIVERED means the OS notification call was accepted (best effort)."""

    due_at: datetime
    status: ReminderStatus
    updated_at: datetime
    delivered_at: datetime | None = None

    def __post_init__(self) -> None:
        try:
            object.__setattr__(self, "status", ReminderStatus(self.status))
        except ValueError:
            raise ValidationError("Reminder status is not recognized.") from None
        object.__setattr__(self, "due_at", utc_datetime(self.due_at))
        object.__setattr__(self, "updated_at", utc_datetime(self.updated_at))
        if self.delivered_at is not None:
            object.__setattr__(self, "delivered_at", utc_datetime(self.delivered_at))
        if (self.status is ReminderStatus.DELIVERED) != (self.delivered_at is not None):
            raise ValidationError("Only a delivered reminder has a delivery time.")

    @classmethod
    def schedule(cls, due_at: datetime, now: datetime) -> "Reminder":
        """A new ACTIVE reminder; also the only way back to ACTIVE (reschedule)."""
        now, due_at = utc_datetime(now), utc_datetime(due_at)
        if due_at <= now:
            raise ValidationError("Reminder time must be in the future.")
        return cls(due_at, ReminderStatus.ACTIVE, now)

    def cancelled(self, now: datetime) -> "Reminder":
        return replace(
            self, status=ReminderStatus.CANCELLED, delivered_at=None, updated_at=utc_datetime(now)
        )

    def delivered(self, now: datetime) -> "Reminder":
        if self.status is not ReminderStatus.ACTIVE:
            raise ValidationError("Only an active reminder can be delivered.")
        now = utc_datetime(now)
        return replace(self, status=ReminderStatus.DELIVERED, delivered_at=now, updated_at=now)

    def is_due(self, now: datetime) -> bool:
        return self.status is ReminderStatus.ACTIVE and self.due_at <= utc_datetime(now)
