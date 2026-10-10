"""Immutable list/search contracts; repository criteria contain aware UTC bounds."""

from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum

from noteapp.domain.value_objects.priority import Priority


@dataclass(frozen=True)
class ListNotesInput:
    limit: int = 30
    cursor: str | None = None


class DateField(str, Enum):
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"


class SortMode(str, Enum):
    UPDATED_AT = "updated_at"
    CREATED_AT = "created_at"
    PRIORITY = "priority"
    CATEGORY = "category"


class SortDirection(str, Enum):
    ASC = "ASC"
    DESC = "DESC"


@dataclass(frozen=True)
class SearchNotesCriteria:
    text: str = ""
    category_id: str | None = None
    priority: Priority | None = None
    start_date: date | None = None
    end_date: date | None = None
    date_field: DateField = DateField.UPDATED_AT
    sort: SortMode = SortMode.UPDATED_AT
    direction: SortDirection = SortDirection.DESC
    limit: int = 30
    cursor: str | None = None


@dataclass(frozen=True)
class CompiledNoteCriteria:
    text: str
    category_id: str | None
    priority: Priority | None
    utc_start: datetime | None
    utc_end_exclusive: datetime | None
    date_field: DateField
    sort: SortMode
    direction: SortDirection
    limit: int
    cursor: str | None
