"""P3B-01: reminder state machine and time policy with a fake clock."""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from noteapp.domain.entities.reminder import Reminder, ReminderStatus
from noteapp.domain.errors import ValidationError
from noteapp.domain.policies.reminder_policy import local_to_utc, retry_delay
from tests.fakes import FakeClock

NOW = FakeClock().now()
BERLIN = ZoneInfo("Europe/Berlin")


def test_schedule_requires_a_strictly_future_time():
    reminder = Reminder.schedule(NOW + timedelta(seconds=1), NOW)
    assert reminder.status is ReminderStatus.ACTIVE and reminder.delivered_at is None
    for due in (NOW, NOW - timedelta(days=1)):
        with pytest.raises(ValidationError):
            Reminder.schedule(due, NOW)


def test_naive_timestamps_are_rejected():
    with pytest.raises(ValidationError):
        Reminder.schedule(datetime(2030, 1, 1), NOW)
    with pytest.raises(ValidationError):
        Reminder(datetime(2030, 1, 1), ReminderStatus.ACTIVE, NOW)


def test_times_are_normalized_to_utc():
    local = datetime(2026, 11, 1, 9, tzinfo=BERLIN)
    reminder = Reminder.schedule(local, NOW)
    assert reminder.due_at.tzinfo == timezone.utc and reminder.due_at.hour == 8


def test_delivery_only_from_active_and_records_time():
    active = Reminder.schedule(NOW + timedelta(hours=1), NOW)
    later = NOW + timedelta(hours=2)
    delivered = active.delivered(later)
    assert delivered.status is ReminderStatus.DELIVERED and delivered.delivered_at == later
    with pytest.raises(ValidationError):
        delivered.delivered(later)
    with pytest.raises(ValidationError):
        active.cancelled(later).delivered(later)


def test_cancelled_is_never_due_and_delivered_is_not_polled_as_active():
    active = Reminder.schedule(NOW + timedelta(hours=1), NOW)
    after = NOW + timedelta(hours=3)
    assert active.is_due(after) and not active.is_due(NOW)
    assert not active.cancelled(after).is_due(after)
    assert not active.delivered(after).is_due(after)


def test_delivery_time_and_status_must_agree():
    with pytest.raises(ValidationError):
        Reminder(NOW, ReminderStatus.ACTIVE, NOW, delivered_at=NOW)
    with pytest.raises(ValidationError):
        Reminder(NOW, ReminderStatus.DELIVERED, NOW)
    with pytest.raises(ValidationError):
        Reminder(NOW, "SNOOZED", NOW)


def test_local_time_converts_with_the_given_zone():
    assert local_to_utc(datetime(2026, 11, 1, 21), BERLIN) == datetime(
        2026, 11, 1, 20, tzinfo=timezone.utc
    )
    assert local_to_utc(datetime(2026, 7, 1, 21), BERLIN).hour == 19  # summer offset


def test_aware_values_need_no_zone():
    value = datetime(2026, 11, 1, 21, tzinfo=timezone(timedelta(hours=7)))
    assert local_to_utc(value, None) == datetime(2026, 11, 1, 14, tzinfo=timezone.utc)


def test_missing_zone_is_an_error_not_a_guess():
    with pytest.raises(ValidationError):
        local_to_utc(datetime(2026, 11, 1, 21), None)


def test_dst_gap_is_rejected():
    with pytest.raises(ValidationError, match="does not exist"):
        local_to_utc(datetime(2027, 3, 28, 2, 30), BERLIN)


def test_dst_overlap_is_rejected_instead_of_guessed():
    with pytest.raises(ValidationError, match="ambiguous"):
        local_to_utc(datetime(2026, 10, 25, 2, 30), BERLIN)


def test_times_next_to_dst_changes_are_fine():
    assert local_to_utc(datetime(2026, 10, 25, 1, 59), BERLIN).hour == 23
    assert local_to_utc(datetime(2026, 10, 25, 3, 0), BERLIN).hour == 2
    assert local_to_utc(datetime(2027, 3, 28, 3, 0), BERLIN).hour == 1


def test_non_datetime_is_rejected():
    with pytest.raises(ValidationError):
        local_to_utc("2026-11-01 21:00", BERLIN)


def test_retry_delay_grows_then_is_capped():
    assert retry_delay(1) == timedelta(minutes=1)
    assert retry_delay(2) == timedelta(minutes=5)
    assert retry_delay(9) == timedelta(minutes=5)
