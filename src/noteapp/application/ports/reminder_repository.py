"""Reminder persistence: CAS configuration plus an atomic, lease-based delivery claim."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable

from noteapp.domain.entities.note import Note


@dataclass(frozen=True)
class ClaimedReminder:
    note_id: str
    title: str
    due_at: datetime
    claim_token: str
    attempts: int


@runtime_checkable
class ReminderRepository(Protocol):
    def set_reminder_if_version(self, note: Note, expected_version: int) -> bool:
        """Atomically store note.reminder (or clear it) on an active note.

        note.version must be expected_version + 1. Replaces any claim in flight. Returns False
        when the note is missing, trashed or at another version; other fields are not written.
        A CANCELLED reminder is only stored over an ACTIVE one, so a delivery that already
        happened is never rewritten as cancelled.
        """

    def claim_next_due(
        self, now: datetime, lease_until: datetime, claim_token: str, max_attempts: int
    ) -> ClaimedReminder | None:
        """Atomically claim one ACTIVE reminder with due_at <= now on an active note.

        Skips reminders under a live lease or a retry delay, or with max_attempts used up.
        Counts the claim as an attempt. Two concurrent callers never get the same reminder.
        """

    def mark_delivered(self, note_id: str, claim_token: str, now: datetime) -> bool:
        """ACTIVE -> DELIVERED iff claim_token still owns the reminder (else False)."""

    def release_claim(self, note_id: str, claim_token: str, retry_at: datetime) -> bool:
        """Give the claim up after a failed attempt; not claimable again before retry_at."""
