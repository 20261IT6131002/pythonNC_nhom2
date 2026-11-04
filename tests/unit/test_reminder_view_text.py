"""P3B-04: local-time formatting and dialog input parsing without a display."""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from noteapp.application.dto.note_view import ReminderView
from noteapp.presentation.tk.views.note_editor import describe_reminder
from noteapp.presentation.tk.views.reminder_dialog import parse_local_datetime

NOW = datetime(2026, 10, 25, 12, tzinfo=timezone.utc)
HANOI = ZoneInfo("Asia/Ho_Chi_Minh")


def view(status, due=NOW + timedelta(hours=9), delivered=None):
    return ReminderView(due, status, delivered)


def test_active_reminder_is_shown_in_the_local_zone_not_utc():
    text = describe_reminder(view("ACTIVE"), HANOI, NOW)
    assert text == "Nhắc nhở: 04:00 26/10/2026"  # 21:00 UTC -> 04:00 next day in UTC+7


def test_overdue_active_reminder_says_it_is_waiting_for_delivery():
    text = describe_reminder(view("ACTIVE", NOW - timedelta(minutes=1)), HANOI, NOW)
    assert "đang chờ gửi" in text


def test_other_states_have_their_own_wording():
    assert describe_reminder(None, HANOI, NOW) == "Chưa đặt nhắc nhở."
    assert describe_reminder(view("CANCELLED"), HANOI, NOW) == "Đã hủy nhắc nhở."
    delivered = view("DELIVERED", delivered=NOW)
    assert describe_reminder(delivered, HANOI, NOW).startswith("Đã nhắc lúc 04:00")


@pytest.mark.parametrize(
    ("date", "time", "expected"),
    [
        ("25/10/2026", "21:00", datetime(2026, 10, 25, 21)),
        (" 1/2/2027 ", " 7:05 ", datetime(2027, 2, 1, 7, 5)),
    ],
)
def test_dialog_accepts_day_first_dates_and_24_hour_time(date, time, expected):
    assert parse_local_datetime(date, time) == expected


@pytest.mark.parametrize(
    ("date", "time"),
    [
        ("2026-10-25", "21:00"),
        ("31/02/2026", "10:00"),
        ("25/10/2026", "25:00"),
        ("", ""),
        ("25/10/2026", "9pm"),
    ],
)
def test_dialog_rejects_malformed_input(date, time):
    with pytest.raises(ValueError):
        parse_local_datetime(date, time)
