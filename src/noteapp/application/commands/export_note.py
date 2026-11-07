"""FR-15 exports an authorized, persisted note revision."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol

from noteapp.application.ports.attachment_store import AttachmentStore
from noteapp.application.ports.note_repository import NoteRepository
from noteapp.application.services.attachment_service import read_verified_attachment
from noteapp.domain.errors import Conflict, ExportLocked, NotFound, ValidationError
from noteapp.domain.policies.note_validation import validate_id, validate_version


class ExportFormat(str, Enum):
    MARKDOWN = "markdown"
    PDF = "pdf"


@dataclass(frozen=True)
class ExportNoteInput:
    note_id: str
    expected_version: int
    directory: str = field(repr=False)
    format: ExportFormat


@dataclass(frozen=True)
class ExportImage:
    mime_type: str
    data: bytes = field(repr=False)


@dataclass(frozen=True)
class ExportSnapshot:
    title: str = field(repr=False)
    content: str = field(repr=False)
    image: ExportImage | None = None


class NoteExporter(Protocol):
    def publish(self, snapshot: ExportSnapshot, directory: str, format: ExportFormat) -> str:
        """Publish a complete file or bundle and return its main file path."""


class ExportNote:
    def __init__(
        self, notes: NoteRepository, attachments: AttachmentStore, exporter: NoteExporter
    ) -> None:
        self.notes, self.attachments, self.exporter = notes, attachments, exporter

    def execute(self, command: ExportNoteInput) -> str:
        validate_id(command.note_id)
        validate_version(command.expected_version)
        if not isinstance(command.format, ExportFormat):
            raise ValidationError("Unsupported export format.")
        note = self.notes.find_by_id(command.note_id)
        if note is None:
            raise NotFound("Active note not found.")
        if note.is_locked or note.content is None:
            raise ExportLocked("Locked notes cannot be exported.")
        if note.version != command.expected_version:
            raise Conflict("Reload the latest note before exporting.")
        image = None
        if note.attachment is not None:
            ref = note.attachment
            image = ExportImage(ref.mime_type, read_verified_attachment(self.attachments, ref))
            current = self.notes.find_by_id(command.note_id)
            if current is None or current.version != note.version or current.is_locked:
                raise Conflict("The note changed while reading its attachment.")
        snapshot = ExportSnapshot(note.title, note.content, image)
        return self.exporter.publish(snapshot, command.directory, command.format)
