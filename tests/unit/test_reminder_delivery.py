"""P3B-05/06/09: delivery service rules with fake repository, gateway and clock."""

from datetime import timedelta

import pytest

from noteapp.application.services.reminder_service import (
    ReminderDeliveryService,
    notification_message,
)
from noteapp.domain.entities.reminder import Reminder, ReminderStatus
from noteapp.domain.errors import NotificationFailure, RepositoryUnavailable
from noteapp.domain.policies.reminder_policy import MAX_DELIVERY_ATTEMPTS
from tests.fakes import FakeClock
from tests.reminder_fakes import FakeGateway, FakeReminderNotes, RaisingGateway
from tests.repository_contracts import note


class World:
    def __init__(self, gateway=None):
        self.notes, self.clock = FakeReminderNotes(), FakeClock()
        self.gateway = gateway if gateway is not None else FakeGateway()
        self.service = ReminderDeliveryService(self.notes, self.gateway, self.clock)

    def remind(self, due_in=timedelta(minutes=5), title="Họp nhóm"):
        now = self.clock.now()
        saved = self.notes.create(note(title=title), title + str(len(self.notes.items)))
        updated = saved.with_reminder(Reminder.schedule(now + due_in, now), now)
        assert self.notes.set_reminder_if_version(updated, saved.version)
        return saved.id

    def reminder(self, note_id):
        return self.notes.find_by_id(note_id).reminder

    def advance(self, **delta):
        self.clock.value += timedelta(**delta)


@pytest.fixture
def world():
    return World()


def test_nothing_due_means_no_notification(world):
    world.remind()
    report = world.service.deliver_due()
    assert report.delivered == () and world.gateway.sent == []


def test_due_reminder_is_notified_once_and_marked_delivered(world):
    note_id = world.remind(title="Họp nhóm")
    world.advance(minutes=5)
    report = world.service.deliver_due()
    assert [item.note_id for item in report.delivered] == [note_id]
    assert world.gateway.sent == [("Nhắc nhở", "Họp nhóm")]
    assert world.reminder(note_id).status is ReminderStatus.DELIVERED
    assert world.reminder(note_id).delivered_at == world.clock.now()


def test_delivered_reminder_is_not_repeated(world):
    world.remind()
    world.advance(minutes=5)
    world.service.deliver_due()
    world.advance(hours=3)
    assert world.service.deliver_due().delivered == ()
    assert len(world.gateway.sent) == 1


def test_cancelled_reminder_never_notifies(world):
    note_id = world.remind()
    current = world.notes.find_by_id(note_id)
    now = world.clock.now()
    world.notes.items[note_id] = current.with_reminder(current.reminder.cancelled(now), now)
    world.advance(days=1)
    assert world.service.deliver_due().delivered == () and world.gateway.sent == []


def test_trashed_note_is_silent_and_fires_after_restore(world):
    note_id = world.remind()
    world.notes.trash(note_id)
    world.advance(minutes=10)
    assert world.service.deliver_due().delivered == ()
    world.notes.trashed.discard(note_id)  # restore: the overdue reminder follows missed policy
    assert [i.note_id for i in world.service.deliver_due().delivered] == [note_id]


def test_missed_reminders_after_restart_are_delivered_once_each_in_due_order(world):
    late = world.remind(timedelta(minutes=30), "Muộn")
    early = world.remind(timedelta(minutes=5), "Sớm")
    world.advance(hours=2)  # the app was closed for two hours
    report = world.service.deliver_due()
    assert [item.note_id for item in report.delivered] == [early, late]
    assert [message for _, message in world.gateway.sent] == ["Sớm", "Muộn"]
    assert world.service.deliver_due().delivered == ()


def test_os_failure_keeps_the_app_healthy_and_retries_later():
    world = World(FakeGateway())
    note_id = world.remind()
    world.advance(minutes=5)
    world.gateway.error = NotificationFailure("no dbus")
    report = world.service.deliver_due()
    assert report.failed == 1 and report.delivered == ()
    assert world.reminder(note_id).status is ReminderStatus.ACTIVE
    world.gateway.error = None
    assert world.service.deliver_due().delivered == ()  # still inside the retry delay
    world.advance(minutes=1)
    assert [i.note_id for i in world.service.deliver_due().delivered] == [note_id]


def test_unexpected_provider_exception_is_contained_and_not_leaked(caplog):
    world = World(RaisingGateway())
    note_id = world.remind()
    world.advance(minutes=5)
    with caplog.at_level("WARNING", logger="noteapp.reminders"):
        report = world.service.deliver_due()
    assert report.failed == 1 and world.reminder(note_id).status is ReminderStatus.ACTIVE
    assert "secret path" not in caplog.text and "/home/" not in caplog.text


def test_retries_are_bounded_so_a_broken_provider_never_loops():
    world = World(FakeGateway())
    world.gateway.error = NotificationFailure("down")
    note_id = world.remind()
    world.advance(minutes=5)
    for _ in range(10):
        world.service.deliver_due()
        world.advance(minutes=10)
    assert world.notes.attempts(note_id) == MAX_DELIVERY_ATTEMPTS
    assert world.reminder(note_id).status is ReminderStatus.ACTIVE  # honest: not DELIVERED


def test_database_outage_is_reported_not_raised_and_recovers(world):
    note_id = world.remind()
    world.advance(minutes=5)
    world.notes.fail = RepositoryUnavailable("down")
    report = world.service.deliver_due()
    assert report.unavailable and report.delivered == () and world.gateway.sent == []
    world.notes.fail = None
    assert [i.note_id for i in world.service.deliver_due().delivered] == [note_id]


def test_lost_mark_after_notify_is_reported_and_the_lease_blocks_a_duplicate(world):
    note_id = world.remind()
    world.advance(minutes=5)
    original = world.notes.mark_delivered

    def unavailable(*_):
        raise RepositoryUnavailable("down")

    world.notes.mark_delivered = unavailable
    assert world.service.deliver_due().unavailable
    world.notes.mark_delivered = original
    world.advance(seconds=30)  # inside the lease: no duplicate yet
    assert world.service.deliver_due().delivered == () and len(world.gateway.sent) == 1
    assert world.reminder(note_id).status is ReminderStatus.ACTIVE


def test_should_continue_stops_the_batch_early(world):
    for _ in range(3):
        world.remind()
    world.advance(minutes=10)
    calls = iter([True, False])
    report = world.service.deliver_due(lambda: next(calls))
    assert len(report.delivered) == 1


def test_batch_size_limits_one_pass(world):
    world.service.batch_size = 2
    for _ in range(3):
        world.remind()
    world.advance(minutes=10)
    assert len(world.service.deliver_due().delivered) == 2
    assert len(world.service.deliver_due().delivered) == 1


def test_notification_text_is_plain_bounded_and_single_line():
    assert notification_message("a\nb\t c") == "a b c"
    assert len(notification_message("x" * 500)) == 120
    assert notification_message("x" * 500).endswith("…")
