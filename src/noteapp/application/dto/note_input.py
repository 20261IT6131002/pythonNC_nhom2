"""Immutable public input contracts."""

from dataclasses import dataclass

from noteapp.domain.value_objects.priority import Priority

__all__ = ["CreateNoteInput", "UpdateNoteInput", "Priority"]


@dataclass(frozen=True)
class CreateNoteInput:
    title: str
    content: str
    priority: Priority
    category_id: str | None
    client_operation_id: str


@dataclass(frozen=True)
class UpdateNoteInput:
    note_id: str
    title: str
    content: str
    priority: Priority
    category_id: str | None
    expected_version: int


@dataclass(frozen=True)
class TrashNoteInput:
    note_id: str
    expected_version: int


@dataclass(frozen=True)
class RestoreNoteInput:
    note_id: str
    expected_version: int


@dataclass(frozen=True)
class PurgeNoteInput:
    note_id: str
    expected_version: int
    confirmed: bool = False


@dataclass(frozen=True)
class ListTrashInput:
    limit: int = 30
    cursor: str | None = None
