"""P2-03/04: validation before I/O and real IANA date/fold/gap boundaries."""

from dataclasses import replace
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from noteapp.application.dto.note_filter import SearchNotesCriteria, SortDirection, SortMode
from noteapp.application.ports.note_repository import NotePage
from noteapp.application.queries.search_notes import SearchNotes
from noteapp.domain.errors import ValidationError
from noteapp.domain.value_objects.time_range import local_date_bounds


class CaptureQuery:
    def __init__(self):
        self.calls = []

    def search(self, criteria):
        self.calls.append(criteria)
        return NotePage((), None)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("text", {"$ne": None}),
        ("text", None),
        ("category_id", ""),
        ("category_id", {"$where": "unsafe"}),
        ("priority", "INVALID"),
        ("sort", "$where"),
        ("direction", "invalid"),
        ("date_field", "title"),
        ("limit", True),
        ("limit", 0),
        ("limit", 101),
        ("cursor", ""),
        ("cursor", {}),
        ("cursor", "x" * 2049),
        ("start_date", "2026-10-10"),
        ("start_date", datetime(2026, 10, 10)),
    ],
)
def test_invalid_criteria_never_queries(field, value):
    repo = CaptureQuery()
    with pytest.raises(ValidationError):
        SearchNotes(repo, ZoneInfo("Asia/Ho_Chi_Minh")).execute(
            replace(SearchNotesCriteria(), **{field: value})
        )
    assert not repo.calls


def test_strings_are_text_not_query_operators():
    repo = CaptureQuery()
    query = SearchNotes(repo, None)
    query.execute(SearchNotesCriteria(text='  {"$where":"unsafe"}  '))
    assert repo.calls[0].text == '{"$where":"unsafe"}'
    assert repo.calls[0].utc_start is None


@pytest.mark.parametrize(
    ("key", "day", "hours"),
    [
        ("Asia/Ho_Chi_Minh", date(2026, 10, 10), 24),
        ("America/New_York", date(2026, 3, 8), 23),
        ("America/New_York", date(2026, 11, 1), 25),
    ],
)
def test_inclusive_day_uses_real_timezone(key, day, hours):
    start, end = local_date_bounds(day, day, ZoneInfo(key))
    assert (end - start).total_seconds() == hours * 3600
    assert start.tzinfo == end.tzinfo == timezone.utc
    if key == "Asia/Ho_Chi_Minh":
        assert start == datetime(2026, 10, 9, 17, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    ("key", "day"),
    [("Pacific/Apia", date(2011, 12, 30)), ("America/Havana", date(2020, 11, 1))],
)
def test_nonexistent_or_ambiguous_midnight_rejected(key, day):
    with pytest.raises(ValidationError):
        local_date_bounds(day, day, ZoneInfo(key))


def test_bad_range_overflow_and_missing_timezone():
    for start, end, zone in (
        (date(2026, 10, 11), date(2026, 10, 10), ZoneInfo("UTC")),
        (None, date.max, ZoneInfo("UTC")),
        (date(2026, 10, 10), None, None),
    ):
        with pytest.raises(ValidationError):
            local_date_bounds(start, end, zone)
    assert local_date_bounds(None, None, None) == (None, None)


def test_single_sided_range_and_unsupported_direction():
    repo = CaptureQuery()
    query = SearchNotes(repo, ZoneInfo("UTC"))
    query.execute(SearchNotesCriteria(start_date=date(2026, 10, 10)))
    assert repo.calls[-1].utc_start is not None
    assert repo.calls[-1].utc_end_exclusive is None
    with pytest.raises(ValidationError):
        query.execute(SearchNotesCriteria(sort=SortMode.CATEGORY, direction=SortDirection.DESC))
