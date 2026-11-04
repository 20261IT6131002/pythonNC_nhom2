"""ReminderRepository behavior shared by the in-memory fake and the Mongo adapter.

Concrete classes provide a `world` fixture with: notes (NoteRepository), reminders
(ReminderRepository), trash(note_id) and a FakeClock named clock.
"""

from dataclasses import replace
from datetime import timedelta
from secrets import token_hex
from uuid import uuid4

from noteapp.domain.entities.reminder import Reminder, ReminderStatus
from tests.repository_contracts import note

MAX = 3


def make(world, due_in=timedelta(minutes=10), title="Ghi chú"):
    """A saved note whose ACTIVE reminder is due `due_in` after the world clock."""
    now = world.clock.now()
    saved = world.notes.create(note(title=title), str(uuid4()))
    updated = saved.with_reminder(Reminder.schedule(now + due_in, now), now)
    assert world.reminders.set_reminder_if_version(updated, saved.version)
    return world.notes.find_by_id(saved.id)


def claim(world, at, lease=timedelta(minutes=2)):
    return world.reminders.claim_next_due(at, at + lease, token_hex(8), MAX)


class ReminderRepositoryContract:
    def test_set_persists_active_reminder_and_advances_version_once(self, world):
        saved = make(world)
        assert saved.version == 2
        assert saved.reminder.status is ReminderStatus.ACTIVE
        assert saved.reminder.due_at == world.clock.now() + timedelta(minutes=10)

    def test_set_with_stale_version_changes_nothing(self, world):
        saved = make(world)
        stale = replace(saved, reminder=None)  # built from version 1, but the note is at 2
        assert not world.reminders.set_reminder_if_version(stale, saved.version - 1)
        assert world.notes.find_by_id(saved.id).reminder == saved.reminder

    def test_set_on_trashed_note_is_refused(self, world):
        saved = make(world)
        world.trash(saved.id)
        cleared = saved.with_reminder(None, world.clock.now())
        assert not world.reminders.set_reminder_if_version(cleared, saved.version)

    def test_clearing_removes_the_reminder(self, world):
        saved = make(world)
        cleared = saved.with_reminder(None, world.clock.now())
        assert world.reminders.set_reminder_if_version(cleared, saved.version)
        assert world.notes.find_by_id(saved.id).reminder is None

    def test_not_claimable_before_due_and_claimable_at_due(self, world):
        saved = make(world)
        due = saved.reminder.due_at
        assert claim(world, due - timedelta(seconds=1)) is None
        claimed = claim(world, due)
        assert claimed.note_id == saved.id and claimed.title == saved.title
        assert claimed.due_at == due and claimed.attempts == 1

    def test_second_claim_cannot_take_the_same_reminder(self, world):
        saved = make(world)
        assert claim(world, saved.reminder.due_at) is not None
        assert claim(world, saved.reminder.due_at) is None

    def test_claim_does_not_change_version_or_updated_at(self, world):
        saved = make(world)
        claim(world, saved.reminder.due_at)
        after = world.notes.find_by_id(saved.id)
        assert (after.version, after.updated_at) == (saved.version, saved.updated_at)

    def test_earliest_due_is_claimed_first(self, world):
        late = make(world, timedelta(minutes=30))
        early = make(world, timedelta(minutes=5))
        at = late.reminder.due_at
        assert claim(world, at).note_id == early.id
        assert claim(world, at).note_id == late.id

    def test_trashed_cancelled_and_delivered_are_never_claimed(self, world):
        trashed, cancelled, delivered = make(world), make(world), make(world)
        now = world.clock.now()
        world.trash(trashed.id)
        off = cancelled.with_reminder(cancelled.reminder.cancelled(now), now)
        assert world.reminders.set_reminder_if_version(off, cancelled.version)
        at = delivered.reminder.due_at
        first = claim(world, at)
        assert first.note_id == delivered.id  # the only eligible one
        assert world.reminders.mark_delivered(first.note_id, first.claim_token, at)
        assert claim(world, at + timedelta(days=1)) is None

    def test_mark_delivered_needs_the_owning_token(self, world):
        saved = make(world)
        claimed = claim(world, saved.reminder.due_at)
        at = saved.reminder.due_at
        assert not world.reminders.mark_delivered(saved.id, "wrong-token", at)
        assert world.reminders.mark_delivered(saved.id, claimed.claim_token, at)
        reminder = world.notes.find_by_id(saved.id).reminder
        assert reminder.status is ReminderStatus.DELIVERED and reminder.delivered_at == at
        assert not world.reminders.mark_delivered(saved.id, claimed.claim_token, at)

    def test_release_delays_the_retry_and_counts_attempts(self, world):
        saved = make(world)
        at = saved.reminder.due_at
        first = claim(world, at)
        retry_at = at + timedelta(minutes=1)
        assert world.reminders.release_claim(saved.id, first.claim_token, retry_at)
        assert claim(world, retry_at - timedelta(seconds=1)) is None
        second = claim(world, retry_at)
        assert second.note_id == saved.id and second.attempts == 2

    def test_attempts_are_bounded(self, world):
        saved = make(world)
        at = saved.reminder.due_at
        for expected in range(1, MAX + 1):
            claimed = claim(world, at)
            assert claimed.attempts == expected
            assert world.reminders.release_claim(saved.id, claimed.claim_token, at)
        assert claim(world, at + timedelta(days=1)) is None
        assert world.notes.find_by_id(saved.id).reminder.status is ReminderStatus.ACTIVE

    def test_expired_lease_makes_the_reminder_claimable_again(self, world):
        saved = make(world)
        at = saved.reminder.due_at
        first = claim(world, at, lease=timedelta(minutes=2))
        assert claim(world, at + timedelta(minutes=1)) is None
        again = claim(world, at + timedelta(minutes=3))
        assert again.note_id == saved.id and again.attempts == 2
        assert not world.reminders.mark_delivered(saved.id, first.claim_token, at)

    def test_reschedule_after_claim_discards_the_old_claim(self, world):
        saved = make(world)
        at = saved.reminder.due_at
        claimed = claim(world, at)
        current = world.notes.find_by_id(saved.id)
        later = current.with_reminder(Reminder.schedule(at + timedelta(hours=1), at), at)
        assert world.reminders.set_reminder_if_version(later, current.version)
        assert not world.reminders.mark_delivered(saved.id, claimed.claim_token, at)
        assert not world.reminders.release_claim(saved.id, claimed.claim_token, at)
        assert world.notes.find_by_id(saved.id).reminder.status is ReminderStatus.ACTIVE
        assert claim(world, at) is None  # the new due time has not been reached
        assert claim(world, at + timedelta(hours=1)).note_id == saved.id

    def test_cancel_after_claim_prevents_delivery_mark(self, world):
        saved = make(world)
        at = saved.reminder.due_at
        claimed = claim(world, at)
        current = world.notes.find_by_id(saved.id)
        off = current.with_reminder(current.reminder.cancelled(at), at)
        assert world.reminders.set_reminder_if_version(off, current.version)
        assert not world.reminders.mark_delivered(saved.id, claimed.claim_token, at)
        assert world.notes.find_by_id(saved.id).reminder.status is ReminderStatus.CANCELLED

    def test_cancelled_never_overwrites_a_delivery(self, world):
        saved = make(world)
        at = saved.reminder.due_at
        claimed = claim(world, at)
        assert world.reminders.mark_delivered(saved.id, claimed.claim_token, at)
        stale_cancel = saved.with_reminder(saved.reminder.cancelled(at), at)
        assert not world.reminders.set_reminder_if_version(stale_cancel, saved.version)
        assert world.notes.find_by_id(saved.id).reminder.status is ReminderStatus.DELIVERED

    def test_reschedule_after_delivery_returns_to_active_and_fires_again(self, world):
        saved = make(world)
        at = saved.reminder.due_at
        claimed = claim(world, at)
        assert world.reminders.mark_delivered(saved.id, claimed.claim_token, at)
        current = world.notes.find_by_id(saved.id)
        again = current.with_reminder(Reminder.schedule(at + timedelta(hours=2), at), at)
        assert world.reminders.set_reminder_if_version(again, current.version)
        assert claim(world, at + timedelta(hours=2)).note_id == saved.id
