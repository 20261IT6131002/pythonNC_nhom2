"""Discover and classify local drafts independently from Mongo availability."""

from noteapp.application.dto.local_draft import (
    DraftAck,
    DraftHeader,
    RecoveryDecision,
    RecoveryKind,
)
from noteapp.application.dto.note_view import NoteView
from noteapp.application.ports.clock import Clock
from noteapp.application.ports.draft_store import DraftStore
from noteapp.application.ports.note_repository import NoteRepository
from noteapp.application.services.draft_autosave import DraftAutosave
from noteapp.domain.errors import (
    AuthenticationFailed,
    RepositoryUnavailable,
    SecureStorageUnavailable,
    ValidationError,
)


class DraftRecoveryService:
    def __init__(self, store: DraftStore, notes: NoteRepository, clock: Clock) -> None:
        self.store = store
        self.notes = notes
        self.clock = clock
        self.autosave = DraftAutosave(store)

    def list_recoverable(self) -> tuple[DraftHeader, ...]:
        return self.store.list_recoverable()

    def recover(self, draft_id: str) -> RecoveryDecision:
        try:
            draft = self.store.get(draft_id)
        except (AuthenticationFailed, ValidationError):
            return RecoveryDecision(RecoveryKind.CORRUPT)
        except SecureStorageUnavailable:
            return RecoveryDecision(RecoveryKind.KEY_UNAVAILABLE)

        if draft is None:
            return RecoveryDecision(RecoveryKind.MISSING)

        if draft.source_locked:
            return RecoveryDecision(RecoveryKind.LOCKED_UNSUPPORTED)

        if draft.note_id is None:
            return RecoveryDecision(RecoveryKind.SAFE_NEW, draft)

        try:
            remote = self.notes.find_by_id(draft.note_id)
        except RepositoryUnavailable:
            return RecoveryDecision(RecoveryKind.REMOTE_UNAVAILABLE, draft)

        if remote is None:
            return RecoveryDecision(RecoveryKind.REMOTE_MISSING, draft)

        kind = (
            RecoveryKind.SAFE_EXISTING
            if remote.version == draft.base_version
            else RecoveryKind.REMOTE_CONFLICT
        )

        return RecoveryDecision(kind, draft, NoteView.from_note(remote))

    def acknowledge(self, ack: DraftAck) -> bool:
        return self.store.delete_if_revision(ack.draft_id, ack.revision)

    def discard(self, draft_id: str) -> None:
        self.store.delete(draft_id)
