"""Independent trash port; active Phase1 methods remain unchanged."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from noteapp.domain.entities.note import Note


@dataclass(frozen=True)
class TrashedNote:
    note: Note
    deleted_at: datetime


@dataclass(frozen=True)
class TrashPage:
    items: tuple[TrashedNote, ...]
    next_cursor: str | None


class TrashRepository(Protocol):
    def move_to_trash(self, note_id: str, expected_version: int, now: datetime) -> TrashedNote:
        """Atomically trash an active note or raise a typed error."""

    def restore(self, note_id: str, expected_version: int, now: datetime) -> Note:
        """Restore the same ID from trash with expected version."""

    def list_trashed(self, limit: int, cursor: str | None = None) -> TrashPage:
        """Return one page by deleted_at DESC and ID DESC."""

    def purge_confirmed(self, note_id: str, expected_version: int) -> None:
        """Remove verified text-only trash after explicit intent and CAS."""
