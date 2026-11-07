from typing import Protocol

from noteapp.application.dto.locked_content import LockedContent
from noteapp.domain.entities.note import LockedNote, Note


class LockedNoteRepository(Protocol):
    def find_locked(self, note_id: str) -> tuple[LockedNote, LockedContent] | None:
        """Read active locked metadata and its encrypted payload in one snapshot."""

    def create_locked(self, note: Note, operation_id: str, payload: LockedContent) -> LockedNote:
        """Insert the locked representation directly, idempotently by operation ID."""

    def write_lock(self, note: Note, payload: LockedContent | None, *, was_locked: bool) -> bool:
        """CAS from note.version - 1. None replaces ciphertext with plaintext explicitly."""
