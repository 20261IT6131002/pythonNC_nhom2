"""FR-16 distribution of active notes, including locked notes as metadata counts."""

from dataclasses import dataclass
from typing import Protocol

from noteapp.domain.value_objects.priority import Priority


@dataclass(frozen=True)
class CategoryCount:
    category_id: str | None
    label: str
    count: int


@dataclass(frozen=True)
class StatisticsRow:
    category_id: str | None
    category_name: str | None
    priority: Priority
    count: int


@dataclass(frozen=True)
class NoteStatistics:
    total: int
    categories: tuple[CategoryCount, ...]
    priorities: tuple[tuple[Priority, int], ...]


class NoteStatisticsRepository(Protocol):
    def count_active(self) -> tuple[StatisticsRow, ...]:
        """Return grouped counts from one active-notes aggregation."""


class GetNoteStatistics:
    def __init__(self, repository: NoteStatisticsRepository) -> None:
        self.repository = repository

    def execute(self) -> NoteStatistics:
        priorities = dict.fromkeys((Priority.HIGH, Priority.MEDIUM, Priority.LOW), 0)
        categories: dict[str | None, CategoryCount] = {}
        for row in self.repository.count_active():
            priorities[row.priority] += row.count
            category_id = row.category_id if row.category_name else None
            existing = categories.get(category_id)
            count = row.count + (existing.count if existing else 0)
            categories[category_id] = CategoryCount(
                category_id, row.category_name or "Chưa phân loại", count
            )
        return NoteStatistics(
            sum(priorities.values()),
            tuple(
                sorted(
                    categories.values(),
                    key=lambda entry: (
                        -entry.count,
                        entry.label.casefold(),
                        entry.category_id or "",
                    ),
                )
            ),
            tuple(priorities.items()),
        )
