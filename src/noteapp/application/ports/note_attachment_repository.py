"""Separate port: change only the image reference of a note with optimistic CAS."""

from typing import Protocol, runtime_checkable

from noteapp.domain.entities.note import Note


@runtime_checkable
class NoteAttachmentRepository(Protocol):
    def set_attachment_if_version(self, note: Note, expected_version: int) -> bool:
        """Atomically store note.attachment (or clear it) on an active note.

        note.version must be expected_version + 1. Returns False when the note is
        missing, trashed or at another version; text fields are never written.
        """
