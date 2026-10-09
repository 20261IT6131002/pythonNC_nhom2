"""Phase 1 list input; search/filtering remains deferred."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ListNotesInput:
    limit: int = 30
    cursor: str | None = None
