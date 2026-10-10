"""Read-only active search port, independent of Mongo/Tk."""

from typing import Protocol

from noteapp.application.dto.note_filter import CompiledNoteCriteria
from noteapp.application.ports.note_repository import NotePage


class SearchRepository(Protocol):
    def search(self, criteria: CompiledNoteCriteria) -> NotePage:
        """Return one active-note page, or a typed validation/unavailable error."""
