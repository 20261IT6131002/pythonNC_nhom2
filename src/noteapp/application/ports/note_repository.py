"""Persistence contract; pagination cursor is opaque to core."""

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from noteapp.domain.entities.note import Note


@dataclass(frozen=True)
class NotePage:
    items: tuple[Note, ...]
    next_cursor: str | None


@runtime_checkable
class NoteRepository(Protocol):
    def create(self, note: Note, operation_id: str) -> Note:
        """Persist once per operation ID, returning the first acknowledged note."""

    def find_by_id(self, note_id: str) -> Note | None:
        """Return an active note or None."""

    def list_recent(self, limit: int, cursor: str | None = None) -> NotePage:
        """Return one bounded page ordered by updated_at and ID descending."""

    def update_if_version(self, note: Note, expected_version: int) -> bool:
        """Atomically update an active note iff the expected version matches."""
