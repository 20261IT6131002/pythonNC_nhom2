"""Editor state only; no draft is persisted to disk."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import uuid4

from noteapp.application.dto.note_input import Priority
from noteapp.application.dto.operation_result import ErrorCode


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
    title: str = ""
    content: str = ""
    priority: Priority = Priority.MEDIUM
    category_id: str | None = None
    version: int = 0
    revision: int = 0
    phase: EditorPhase = EditorPhase.CLEAN
    operation_id: str = ""
    error: ErrorCode | None = None
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.operation_id:
            self.operation_id = str(uuid4())

    @property
    def unsaved(self) -> bool:
        return self.phase in {
            EditorPhase.DIRTY,
            EditorPhase.SAVING,
            EditorPhase.ERROR,
            EditorPhase.CONFLICT,
        }
