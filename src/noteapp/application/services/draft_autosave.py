"""Accept immutable snapshots; storage owns atomic revision ordering."""

from noteapp.application.dto.local_draft import LocalDraft
from noteapp.application.ports.draft_store import DraftStore
from noteapp.domain.errors import ValidationError


class DraftAutosave:
    def __init__(self, store: DraftStore, *, locked_notes: bool = False) -> None:
        self.store = store
        self.locked_notes = locked_notes

    def execute(self, draft: LocalDraft) -> bool:
        if draft.source_locked and not self.locked_notes:
            raise ValidationError("Locked draft routing requires the FR-14 save strategy.")

        return self.store.save_if_newer(draft)
