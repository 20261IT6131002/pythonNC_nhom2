"""Recent-list loading and pagination state."""

from dataclasses import dataclass

from noteapp.application.dto.note_view import NoteView, TrashedNoteView
from noteapp.application.dto.operation_result import ErrorCode


@dataclass
class ListState:
    items: tuple[NoteView, ...] = ()
    next_cursor: str | None = None
    loading: bool = False
    error: ErrorCode | None = None
    mode: str = "active"
    generation: int = 0
    trash_items: tuple[TrashedNoteView, ...] = ()
