"""FR-08: one image per note with compensating cleanup around an optimistic note update.

Invariants: new bytes are stored before the note points at them; the previous image is
deleted only after the note update succeeded; a failed update deletes the new bytes and
leaves the previous image referenced. Cleanup failures never fail a completed update; the
orphan reconciler removes unreferenced payloads after its grace period.
"""

import hashlib
import logging

from noteapp.application.dto.note_input import (
    AttachImageFileInput,
    AttachImageInput,
    GetImageInput,
    RemoveImageInput,
)
from noteapp.application.dto.note_view import ImageContent, NoteView
from noteapp.application.ports.attachment_store import AttachmentStore
from noteapp.application.ports.clock import Clock
from noteapp.application.ports.image_file_reader import ImageFileReader
from noteapp.application.ports.image_processor import ImageProcessor
from noteapp.application.ports.note_attachment_repository import NoteAttachmentRepository
from noteapp.application.ports.note_repository import NoteRepository
from noteapp.domain.entities.note import Note
from noteapp.domain.errors import (
    AttachmentStoreFailure,
    Conflict,
    ImageTooLarge,
    NotFound,
    ValidationError,
)
from noteapp.domain.policies.attachment_policy import MAX_IMAGE_BYTES, THUMBNAIL_MAX_WIDTH
from noteapp.domain.policies.note_validation import validate_id, validate_version
from noteapp.domain.value_objects.attachment_ref import AttachmentRef

LOGGER = logging.getLogger("noteapp.attachments")


class AttachmentService:
    def __init__(
        self,
        notes: NoteRepository,
        links: NoteAttachmentRepository,
        store: AttachmentStore,
        images: ImageProcessor,
        clock: Clock,
        files: ImageFileReader | None = None,
    ) -> None:
        self.notes, self.links, self.store, self.images, self.clock = (
            notes,
            links,
            store,
            images,
            clock,
        )
        self.files = files

    def _current(self, note_id: str, expected_version: int) -> Note:
        validate_id(note_id)
        validate_version(expected_version)
        current = self.notes.find_by_id(note_id)
        if current is None:
            raise NotFound("Note not found.")
        if current.version != expected_version:
            raise Conflict("The note has been changed by another editor.")
        return current

    def _discard(self, ref: AttachmentRef | None) -> None:
        """Best-effort delete; a failure leaves an unreferenced payload for the reconciler."""
        if ref is None:
            return
        try:
            self.store.delete(ref)
        except Exception:
            LOGGER.warning("attachment_cleanup_deferred", extra={"stage": "cleanup"})

    def _swap(self, current: Note, updated: Note) -> bool:
        try:
            return self.links.set_attachment_if_version(updated, current.version)
        except Exception:
            self._discard(updated.attachment)
            raise

    def attach(self, command: AttachImageInput) -> NoteView:
        if not isinstance(command.data, bytes | bytearray | memoryview):
            raise ValidationError("Image content must be bytes.")
        if len(command.data) > MAX_IMAGE_BYTES:
            raise ImageTooLarge("Images larger than 10 MiB are not accepted.")
        current = self._current(command.note_id, command.expected_version)
        image = self.images.inspect(bytes(command.data))
        ref = self.store.put(current.id, image, command.display_name)
        updated = current.with_attachment(ref, self.clock.now())
        if not self._swap(current, updated):
            self._discard(ref)
            if self.notes.find_by_id(current.id) is None:
                raise NotFound("Note not found.")
            raise Conflict("The note has been changed by another editor.")
        if current.attachment is not None and current.attachment.storage_key != ref.storage_key:
            self._discard(current.attachment)
        return NoteView.from_note(updated)

    def attach_from_file(self, command: AttachImageFileInput) -> NoteView:
        if self.files is None:
            raise ValidationError("Choosing image files is not configured.")
        validate_id(command.note_id)
        validate_version(command.expected_version)
        data, name = self.files.read(command.path)
        return self.attach(AttachImageInput(command.note_id, command.expected_version, data, name))

    def remove(self, command: RemoveImageInput) -> NoteView:
        current = self._current(command.note_id, command.expected_version)
        if current.attachment is None:
            return NoteView.from_note(current)
        updated = current.with_attachment(None, self.clock.now())
        if not self._swap(current, updated):
            if self.notes.find_by_id(current.id) is None:
                raise NotFound("Note not found.")
            raise Conflict("The note has been changed by another editor.")
        self._discard(current.attachment)
        return NoteView.from_note(updated)

    def get(self, command: GetImageInput) -> ImageContent:
        validate_id(command.note_id)
        if type(command.max_width) is not int or not 1 <= command.max_width <= THUMBNAIL_MAX_WIDTH:
            raise ValidationError("Thumbnail width must be between 1 and 400 pixels.")
        note = self.notes.find_by_id(command.note_id)
        if note is None or note.attachment is None:
            raise NotFound("Image not found.")
        ref = note.attachment
        data = self.store.get(ref)
        if hashlib.sha256(data).hexdigest() != ref.sha256:
            raise AttachmentStoreFailure("Stored image failed its integrity check.")
        thumbnail = self.images.thumbnail(data, command.max_width)
        return ImageContent(
            thumbnail.png,
            thumbnail.width,
            thumbnail.height,
            ref.mime_type,
            ref.size_bytes,
            ref.display_name,
        )
