"""Deterministic reminder ports: in-memory repository with the same claim semantics as Mongo."""

from dataclasses import replace
from threading import Lock

from noteapp.application.ports.reminder_repository import ClaimedReminder
from noteapp.domain.entities.reminder import ReminderStatus
from noteapp.domain.errors import NotificationFailure, ValidationError
from tests.fakes import FakeNotes


class FakeReminderNotes(FakeNotes):
    """FakeNotes plus the ReminderRepository port; trashed notes are invisible."""

    def __init__(self):
        super().__init__()
        self.trashed = set()
        self.claims = {}  # note_id -> {token, until, attempts, retry_at}
        self.fail = None
        self.gate = Lock()

    def find_by_id(self, note_id):
        return None if note_id in self.trashed else super().find_by_id(note_id)

    def trash(self, note_id):
        self.trashed.add(note_id)

    def attempts(self, note_id):
        return self.claims.get(note_id, {}).get("attempts", 0)

    def set_reminder_if_version(self, note, expected_version):
        if self.fail is not None:
            raise self.fail
        if type(expected_version) is not int or expected_version < 1:
            raise ValidationError("Expected version must be a positive integer.")
        if note.version != expected_version + 1:
            raise ValidationError("Version must advance by one.")
        with self.lock:
            current = self.items.get(note.id)
            if current is None or note.id in self.trashed or current.version != expected_version:
                return False
            cancelling = (
                note.reminder is not None and note.reminder.status is ReminderStatus.CANCELLED
            )
            if cancelling and (
                current.reminder is None or current.reminder.status is not ReminderStatus.ACTIVE
            ):
                return False
            self.items[note.id] = note
            self.claims.pop(note.id, None)  # a new configuration replaces any claim
            return True

    def claim_next_due(self, now, lease_until, claim_token, max_attempts):
        if self.fail is not None:
            raise self.fail
        with self.gate:
            due = []
            for note in self.items.values():
                reminder = note.reminder
                meta = self.claims.get(note.id, {})
                if (
                    reminder is None
                    or note.id in self.trashed
                    or reminder.status is not ReminderStatus.ACTIVE
                    or reminder.due_at > now
                    or meta.get("until", now) > now
                    or meta.get("retry_at", now) > now
                    or meta.get("attempts", 0) >= max_attempts
                ):
                    continue
                due.append(note)
            if not due:
                return None
            note = min(due, key=lambda item: (item.reminder.due_at, item.id))
            meta = self.claims.setdefault(note.id, {})
            meta.update(token=claim_token, until=lease_until, attempts=meta.get("attempts", 0) + 1)
            meta.pop("retry_at", None)
            return ClaimedReminder(
                note.id, note.title, note.reminder.due_at, claim_token, meta["attempts"]
            )

    def _owned(self, note_id, token):
        note = self.items.get(note_id)
        meta = self.claims.get(note_id)
        ok = note is not None and note.reminder is not None and meta is not None
        return ok and note.reminder.status is ReminderStatus.ACTIVE and meta.get("token") == token

    def mark_delivered(self, note_id, claim_token, now):
        if self.fail is not None:
            raise self.fail
        with self.gate:
            if not self._owned(note_id, claim_token):
                return False
            note = self.items[note_id]
            self.items[note_id] = replace(note, reminder=note.reminder.delivered(now))
            self.claims.pop(note_id)
            return True

    def release_claim(self, note_id, claim_token, retry_at):
        if self.fail is not None:
            raise self.fail
        with self.gate:
            if not self._owned(note_id, claim_token):
                return False
            meta = self.claims[note_id]
            meta.pop("token"), meta.pop("until")
            meta["retry_at"] = retry_at
            return True


class FakeGateway:
    def __init__(self):
        self.sent = []
        self.error = None

    def notify(self, title, message):
        if self.error is not None:
            raise self.error
        self.sent.append((title, message))


class RaisingGateway:
    """Simulates a provider that leaks internals in its exception text."""

    def notify(self, title, message):
        raise NotificationFailure("secret path /home/user/.config")
