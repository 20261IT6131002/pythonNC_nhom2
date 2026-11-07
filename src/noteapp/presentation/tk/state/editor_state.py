"""Editor content and independent remote/local acknowledgement state."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import uuid4

from noteapp.application.dto.note_input import Priority
from noteapp.application.dto.note_view import AttachmentView, ReminderView
from noteapp.application.dto.operation_result import ErrorCode
from noteapp.presentation.tk.state.sync_state import SyncState


class EditorPhase(str, Enum):
    CLEAN = "CLEAN"
    DIRTY = "DIRTY"
    SAVING = "SAVING"
    SAVED = "SAVED"
    ERROR = "ERROR"
    CONFLICT = "CONFLICT"


@dataclass
class EditorState:
    note_id: str | None = None
    title: str = field(default="", repr=False)
    content: str = field(default="", repr=False)
    priority: Priority = Priority.MEDIUM
    category_id: str | None = None
    version: int = 0
    revision: int = 0
    phase: EditorPhase = EditorPhase.CLEAN
    operation_id: str = ""
    error: ErrorCode | None = None
    updated_at: datetime | None = None
    attachment: AttachmentView | None = None
    reminder: ReminderView | None = None
    is_pinned: bool = False
    draft_id: str = ""
    draft_revision: int = 0
    sync: SyncState = SyncState.REMOTE
    secure_error: ErrorCode | None = None
    source_locked: bool = False
    locked_closed: bool = False

    def __post_init__(self) -> None:
        if not self.operation_id:
            self.operation_id = str(uuid4())
        if not self.draft_id:
            self.draft_id = str(uuid4())

    @property
    def unsaved(self) -> bool:
        return self.phase in {
            EditorPhase.DIRTY,
            EditorPhase.SAVING,
            EditorPhase.ERROR,
            EditorPhase.CONFLICT,
        }
