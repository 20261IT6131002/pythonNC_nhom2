"""Validate a frozen query, normalize local dates, then invoke the read port."""

from datetime import tzinfo

from noteapp.application.dto.note_filter import (
    CompiledNoteCriteria,
    DateField,
    SearchNotesCriteria,
    SortDirection,
    SortMode,
)
from noteapp.application.dto.note_view import NoteListView, NoteView
from noteapp.application.ports.note_query_repository import SearchRepository
from noteapp.domain.errors import ValidationError
from noteapp.domain.policies.note_validation import utc_datetime, validate_id, validate_priority
from noteapp.domain.value_objects.priority import Priority
from noteapp.domain.value_objects.time_range import local_date_bounds


def validate_compiled(criteria: CompiledNoteCriteria) -> None:
    if not isinstance(criteria, CompiledNoteCriteria) or not isinstance(criteria.text, str):
        raise ValidationError("Search must use a typed text criterion.")
    if criteria.category_id is not None:
        validate_id(criteria.category_id)
    if criteria.priority is not None and not isinstance(criteria.priority, Priority):
        raise ValidationError("Priority must be an enum.")
    if not isinstance(criteria.date_field, DateField) or not isinstance(criteria.sort, SortMode):
        raise ValidationError("Invalid date field or sort mode.")
    allowed = {
        SortMode.UPDATED_AT: (SortDirection.DESC,),
        SortMode.CREATED_AT: (SortDirection.ASC, SortDirection.DESC),
        SortMode.PRIORITY: (SortDirection.DESC,),
        SortMode.CATEGORY: (SortDirection.ASC,),
    }
    if (
        not isinstance(criteria.direction, SortDirection)
        or criteria.direction not in allowed[criteria.sort]
    ):
        raise ValidationError("Unsupported sort direction.")
    if type(criteria.limit) is not int or not 1 <= criteria.limit <= 100:
        raise ValidationError("Page size must be between 1 and 100.")
    if criteria.cursor is not None and (
        not isinstance(criteria.cursor, str) or not criteria.cursor or len(criteria.cursor) > 2048
    ):
        raise ValidationError("Invalid search cursor.")
    for bound in (criteria.utc_start, criteria.utc_end_exclusive):
        if bound is not None:
            utc_datetime(bound)
    if (
        criteria.utc_start is not None
        and criteria.utc_end_exclusive is not None
        and criteria.utc_start >= criteria.utc_end_exclusive
    ):
        raise ValidationError("Invalid UTC interval.")


class SearchNotes:
    def __init__(self, repo: SearchRepository, local_timezone: tzinfo | None) -> None:
        self.repo, self.local_timezone = repo, local_timezone

    def execute(self, command: SearchNotesCriteria) -> NoteListView:
        if not isinstance(command, SearchNotesCriteria) or not isinstance(command.text, str):
            raise ValidationError("Search must use typed input.")
        try:
            date_field, sort, direction = (
                DateField(command.date_field),
                SortMode(command.sort),
                SortDirection(command.direction),
            )
        except (TypeError, ValueError):
            raise ValidationError("Invalid date field or sort mode.") from None
        lower, upper = local_date_bounds(command.start_date, command.end_date, self.local_timezone)
        compiled = CompiledNoteCriteria(
            command.text.strip(),
            command.category_id,
            validate_priority(command.priority) if command.priority is not None else None,
            lower,
            upper,
            date_field,
            sort,
            direction,
            command.limit,
            command.cursor,
        )
        validate_compiled(compiled)
        page = self.repo.search(compiled)
        return NoteListView(
            tuple(NoteView.from_note(item) for item in page.items), page.next_cursor
        )
