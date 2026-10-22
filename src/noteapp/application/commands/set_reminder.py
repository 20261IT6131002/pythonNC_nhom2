"""FR-09: set, reschedule and cancel a reminder with optimistic concurrency.

Setting and rescheduling are one operation: both store a new future due time and leave the
reminder ACTIVE, whatever it was before (ACTIVE, DELIVERED or CANCELLED).
"""

from dataclasses import dataclass
from datetime import tzinfo

from noteapp.application.dto.note_input import CancelReminderInput, SetReminderInput
from noteapp.application.dto.note_view import NoteView
from noteapp.application.ports.clock import Clock
from noteapp.application.ports.note_repository import NoteRepository
from noteapp.application.ports.reminder_repository import ReminderRepository
from noteapp.domain.entities.note import Note
from noteapp.domain.entities.reminder import Reminder, ReminderStatus
from noteapp.domain.errors import Conflict, NotFound
from noteapp.domain.policies.note_validation import validate_id, validate_version
from noteapp.domain.policies.reminder_policy import local_to_utc


def _current(notes: NoteRepository, note_id: str, expected_version: int) -> Note:
    validate_id(note_id)
    validate_version(expected_version)
    current = notes.find_by_id(note_id)
    if current is None:
        raise NotFound("Note not found.")
    if current.version != expected_version:
        raise Conflict("The note has been changed by another editor.")
    return current


def _store(notes: NoteRepository, reminders: ReminderRepository, current: Note, updated: Note):
    if not reminders.set_reminder_if_version(updated, current.version):
        latest = notes.find_by_id(current.id)
        if latest is None:
            raise NotFound("Note not found.")
        if (
            updated.reminder is not None
            and updated.reminder.status is ReminderStatus.CANCELLED
            and latest.version == current.version
            and latest.reminder is not None
            and latest.reminder.status is ReminderStatus.DELIVERED
        ):
            return NoteView.from_note(latest)  # it fired just before the cancel: nothing to cancel
        raise Conflict("The note has been changed by another editor.")
    return NoteView.from_note(updated)


class SetReminder:
    def __init__(
        self,
        notes: NoteRepository,
        reminders: ReminderRepository,
        clock: Clock,
        local_timezone: tzinfo | None = None,
    ) -> None:
        self.notes, self.reminders, self.clock = notes, reminders, clock
        self.local_timezone = local_timezone

    def execute(self, command: SetReminderInput) -> NoteView:
        current = _current(self.notes, command.note_id, command.expected_version)
        now = self.clock.now()
        due_at = local_to_utc(command.due_at, self.local_timezone)
        updated = current.with_reminder(Reminder.schedule(due_at, now), now)
        return _store(self.notes, self.reminders, current, updated)


class CancelReminder:
    def __init__(self, notes: NoteRepository, reminders: ReminderRepository, clock: Clock) -> None:
        self.notes, self.reminders, self.clock = notes, reminders, clock

    def execute(self, command: CancelReminderInput) -> NoteView:
        current = _current(self.notes, command.note_id, command.expected_version)
        reminder = current.reminder
        if reminder is None or reminder.status is not ReminderStatus.ACTIVE:
            return NoteView.from_note(current)  # nothing pending: idempotent, no new version
        now = self.clock.now()
        updated = current.with_reminder(reminder.cancelled(now), now)
        return _store(self.notes, self.reminders, current, updated)


@dataclass(frozen=True)
class ReminderTools:
    """Public reminder entry points handed to presentation."""

    set: SetReminder
    cancel: CancelReminder
