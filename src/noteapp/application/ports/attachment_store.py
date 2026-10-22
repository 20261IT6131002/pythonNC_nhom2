"""Attachment storage port: opaque refs in, bytes out; no driver types cross it."""

from typing import Protocol, runtime_checkable

from noteapp.application.ports.image_processor import ValidatedImage
from noteapp.domain.value_objects.attachment_ref import AttachmentRef


@runtime_checkable
class AttachmentStore(Protocol):
    def put(self, owner_note_id: str, image: ValidatedImage, display_name: str) -> AttachmentRef:
        """Store validated bytes (INLINE <= 1 MiB, else GRIDFS) and return a new reference.

        Raises AttachmentStoreFailure when the store did not acknowledge the write.
        """

    def get(self, ref: AttachmentRef) -> bytes:
        """Return the stored bytes or raise AttachmentStoreFailure."""

    def delete(self, ref: AttachmentRef) -> None:
        """Remove the payload. Idempotent: a missing payload is not an error."""

    def exists(self, ref: AttachmentRef) -> bool:
        """Return whether the payload is present."""
