"""Public output models independent of widgets and database drivers."""

from dataclasses import dataclass
from datetime import datetime

from noteapp.domain.entities.category import Category
from noteapp.domain.entities.note import Note
from noteapp.domain.value_objects.priority import Priority


@dataclass(frozen=True)
class NoteView:
    note_id: str
    title: str
    content: str
    priority: Priority
    category_id: str | None
    version: int
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_note(cls, note: Note) -> "NoteView":
        return cls(
            note.id,
            note.title,
            note.content,
            note.priority,
            note.category_id,
            note.version,
            note.created_at,
            note.updated_at,
        )


@dataclass(frozen=True)
class CategoryView:
    category_id: str
    name: str
    color_hex: str

    @classmethod
    def from_category(cls, category: Category) -> "CategoryView":
        return cls(category.id, category.name, category.color_hex)


@dataclass(frozen=True)
class NoteListView:
    items: tuple[NoteView, ...]
    next_cursor: str | None
