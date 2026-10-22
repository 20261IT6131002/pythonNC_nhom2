"""Immutable public input contracts."""

from dataclasses import dataclass, field

from noteapp.domain.value_objects.priority import Priority

__all__ = [
    "CreateNoteInput",
    "UpdateNoteInput",
    "Priority",
    "CreateCategoryInput",
    "RenameCategoryInput",
    "UpdateCategoryColorInput",
    "DeleteCategoryInput",
    "AttachImageInput",
    "RemoveImageInput",
    "GetImageInput",
    "AttachImageFileInput",
]


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


DEFAULT_CATEGORY_COLOR = "#64748B"


@dataclass(frozen=True)
class CreateCategoryInput:
    name: str
    color_hex: str = DEFAULT_CATEGORY_COLOR


@dataclass(frozen=True)
class RenameCategoryInput:
    category_id: str
    name: str


@dataclass(frozen=True)
class UpdateCategoryColorInput:
    category_id: str
    color_hex: str


@dataclass(frozen=True)
class DeleteCategoryInput:
    category_id: str


@dataclass(frozen=True)
class AttachImageInput:
    """Attach, or replace, the single image of a note at expected_version."""

    note_id: str
    expected_version: int
    data: bytes = field(repr=False)
    display_name: str = "image"


@dataclass(frozen=True)
class RemoveImageInput:
    note_id: str
    expected_version: int


@dataclass(frozen=True)
class GetImageInput:
    note_id: str
    max_width: int = 400


@dataclass(frozen=True)
class AttachImageFileInput:
    """Read a user-chosen file in the worker, then attach it like AttachImageInput."""

    note_id: str
    expected_version: int
    path: str
