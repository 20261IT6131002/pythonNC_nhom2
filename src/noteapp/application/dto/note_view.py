"""Public output models independent of widgets and database drivers."""

from dataclasses import dataclass, field
from datetime import datetime

from noteapp.domain.entities.category import Category
from noteapp.domain.entities.note import Note
from noteapp.domain.value_objects.attachment_ref import AttachmentRef
from noteapp.domain.value_objects.priority import Priority


@dataclass(frozen=True)
class AttachmentView:
    """Image metadata for the UI; storage keys and bytes never leave the core."""

    kind: str
    mime_type: str
    size_bytes: int
    display_name: str
    sha256: str = ""

    @classmethod
    def from_ref(cls, ref: AttachmentRef | None) -> "AttachmentView | None":
        if ref is None:
            return None
        return cls(
            ref.storage_kind.value, ref.mime_type, ref.size_bytes, ref.display_name, ref.sha256
        )


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
    attachment: AttachmentView | None = None

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
            AttachmentView.from_ref(note.attachment),
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


@dataclass(frozen=True)
class TrashedNoteView:
    note: NoteView
    deleted_at: datetime


@dataclass(frozen=True)
class TrashListView:
    items: tuple[TrashedNoteView, ...]
    next_cursor: str | None


@dataclass(frozen=True)
class ImageContent:
    """Thumbnail PNG for display plus the metadata of the stored original."""

    png: bytes = field(repr=False)
    width: int
    height: int
    mime_type: str
    size_bytes: int
    display_name: str
