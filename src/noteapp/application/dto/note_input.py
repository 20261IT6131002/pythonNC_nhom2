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
