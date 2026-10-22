"""P3B-03: set / reschedule / cancel use cases; FR-09 acceptance with a fake clock."""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from noteapp.application.commands.set_reminder import CancelReminder, SetReminder
from noteapp.application.dto.note_input import CancelReminderInput, SetReminderInput
from noteapp.domain.entities.reminder import ReminderStatus
from noteapp.domain.errors import Conflict, NotFound, RepositoryUnavailable, ValidationError
from tests.fakes import FakeClock
from tests.reminder_fakes import FakeReminderNotes
from tests.repository_contracts import note

BERLIN = ZoneInfo("Europe/Berlin")


@pytest.fixture
def world():
    notes, clock = FakeReminderNotes(), FakeClock()
    saved = notes.create(note(), "11111111-1111-4111-8111-111111111111")
    return (
        notes,
        clock,
        saved,
        SetReminder(notes, notes, clock, BERLIN),
        CancelReminder(notes, notes, clock),
    )


def future(clock, **delta):
    return clock.now() + timedelta(**delta)


def test_set_future_time_makes_an_active_reminder_and_a_new_version(world):
    notes, clock, saved, set_reminder, _ = world
    view = set_reminder.execute(SetReminderInput(saved.id, 1, future(clock, hours=1)))
    assert view.version == 2 and view.reminder.status == "ACTIVE"
    assert view.reminder.due_at == future(clock, hours=1)
    stored = notes.find_by_id(saved.id)
    assert stored.reminder.status is ReminderStatus.ACTIVE and stored.version == 2
    assert (stored.title, stored.content) == (saved.title, saved.content)


def test_naive_local_time_is_converted_with_the_configured_zone(world):
    notes, clock, saved, set_reminder, _ = world
    view = set_reminder.execute(SetReminderInput(saved.id, 1, datetime(2026, 11, 1, 21)))
    assert view.reminder.due_at == datetime(2026, 11, 1, 20, tzinfo=timezone.utc)


def test_past_or_current_time_is_rejected_and_nothing_is_written(world):
    notes, clock, saved, set_reminder, _ = world
    for due in (clock.now(), future(clock, minutes=-5)):
        with pytest.raises(ValidationError):
            set_reminder.execute(SetReminderInput(saved.id, 1, due))
    assert notes.find_by_id(saved.id) == saved


def test_dst_edges_and_missing_zone_are_validation_errors(world):
    notes, clock, saved, set_reminder, _ = world
    for local in (datetime(2027, 3, 28, 2, 30), datetime(2026, 10, 25, 2, 30)):
        clock.value = datetime(2026, 3, 1, tzinfo=timezone.utc)
        with pytest.raises(ValidationError):
            set_reminder.execute(SetReminderInput(saved.id, 1, local))
    set_reminder.local_timezone = None
    with pytest.raises(ValidationError):
        set_reminder.execute(SetReminderInput(saved.id, 1, datetime(2026, 11, 1, 21)))


def test_reschedule_replaces_the_due_time_and_stays_active(world):
    notes, clock, saved, set_reminder, _ = world
    first = set_reminder.execute(SetReminderInput(saved.id, 1, future(clock, hours=1)))
    second = set_reminder.execute(SetReminderInput(saved.id, 2, future(clock, hours=5)))
    assert second.version == 3 and second.reminder.due_at == future(clock, hours=5)
    assert second.reminder.status == "ACTIVE" and first.reminder.due_at != second.reminder.due_at


@pytest.mark.parametrize("previous", ["DELIVERED", "CANCELLED"])
def test_reschedule_from_delivered_or_cancelled_reactivates(world, previous):
    notes, clock, saved, set_reminder, cancel = world
    set_reminder.execute(SetReminderInput(saved.id, 1, future(clock, hours=1)))
    current = notes.find_by_id(saved.id)
    if previous == "CANCELLED":
        cancel.execute(CancelReminderInput(saved.id, current.version))
    else:
        notes.items[saved.id] = current.with_reminder(
            current.reminder.delivered(future(clock, hours=1)), clock.now()
        )
    current = notes.find_by_id(saved.id)
    assert current.reminder.status.value == previous
    view = set_reminder.execute(SetReminderInput(saved.id, current.version, future(clock, days=1)))
    assert view.reminder.status == "ACTIVE" and view.reminder.delivered_at is None


def test_cancel_persists_the_cancelled_state(world):
    notes, clock, saved, set_reminder, cancel = world
    set_reminder.execute(SetReminderInput(saved.id, 1, future(clock, hours=1)))
    view = cancel.execute(CancelReminderInput(saved.id, 2))
    assert view.reminder.status == "CANCELLED" and view.version == 3
    assert notes.find_by_id(saved.id).reminder.status is ReminderStatus.CANCELLED


def test_cancel_without_pending_reminder_is_a_no_op(world):
    notes, clock, saved, _, cancel = world
    assert cancel.execute(CancelReminderInput(saved.id, 1)).version == 1
    assert notes.find_by_id(saved.id) == saved


def test_stale_version_is_a_conflict_and_leaves_the_note_alone(world):
    notes, clock, saved, set_reminder, cancel = world
    set_reminder.execute(SetReminderInput(saved.id, 1, future(clock, hours=1)))
    with pytest.raises(Conflict):
        set_reminder.execute(SetReminderInput(saved.id, 1, future(clock, hours=9)))
    with pytest.raises(Conflict):
        cancel.execute(CancelReminderInput(saved.id, 1))
    assert notes.find_by_id(saved.id).reminder.due_at == future(clock, hours=1)


def test_concurrent_edit_between_read_and_write_is_a_conflict(world):
    notes, clock, saved, set_reminder, _ = world
    original = notes.set_reminder_if_version

    def lose_race(updated, expected):
        notes.items[saved.id] = saved.edited(
            title="Khác",
            content=saved.content,
            priority=saved.priority,
            category_id=None,
            now=clock.now(),
        )
        return original(updated, expected)

    notes.set_reminder_if_version = lose_race
    with pytest.raises(Conflict):
        set_reminder.execute(SetReminderInput(saved.id, 1, future(clock, hours=1)))
    assert notes.find_by_id(saved.id).reminder is None


def test_missing_or_trashed_note_is_not_found(world):
    notes, clock, saved, set_reminder, cancel = world
    with pytest.raises(NotFound):
        set_reminder.execute(SetReminderInput("f" * 24, 1, future(clock, hours=1)))
    notes.trash(saved.id)
    with pytest.raises(NotFound):
        cancel.execute(CancelReminderInput(saved.id, 1))


def test_repository_failure_surfaces_as_unavailable_without_state_change(world):
    notes, clock, saved, set_reminder, _ = world
    notes.fail = RepositoryUnavailable("down")
    with pytest.raises(RepositoryUnavailable):
        set_reminder.execute(SetReminderInput(saved.id, 1, future(clock, hours=1)))
    notes.fail = None
    assert notes.find_by_id(saved.id).reminder is None


def test_invalid_ids_and_versions_are_rejected_before_any_read(world):
    notes, clock, saved, set_reminder, cancel = world
    with pytest.raises(ValidationError):
        set_reminder.execute(SetReminderInput("", 1, future(clock, hours=1)))
    with pytest.raises(ValidationError):
        cancel.execute(CancelReminderInput(saved.id, 0))


def test_cancel_that_loses_to_a_delivery_is_a_no_op_not_a_conflict(world):
    notes, clock, saved, set_reminder, cancel = world
    view = set_reminder.execute(SetReminderInput(saved.id, 1, future(clock, hours=1)))
    original = notes.find_by_id

    def fire_just_before_cancel_writes(note_id):
        current = original(note_id)
        if current.reminder.status is ReminderStatus.ACTIVE:
            fired = current.reminder.delivered(future(clock, hours=1))
            notes.items[note_id] = current.__class__(**{**current.__dict__, "reminder": fired})
            notes.find_by_id = original  # only the first read returns the stale ACTIVE note
            return current
        return current

    notes.find_by_id = fire_just_before_cancel_writes
    result = cancel.execute(CancelReminderInput(saved.id, view.version))
    assert result.reminder.status == "DELIVERED" and result.version == view.version
    assert notes.find_by_id(saved.id).reminder.status is ReminderStatus.DELIVERED
