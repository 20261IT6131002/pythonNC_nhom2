"""FR-17 immutable snapshots; only draft identity is public in persisted wrappers."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import UUID

from noteapp.application.dto.note_view import NoteView
from noteapp.domain.errors import ValidationError
from noteapp.domain.policies.note_validation import utc_datetime, validate_id, validate_priority
from noteapp.domain.value_objects.priority import Priority

MAX_DRAFT_PAYLOAD_BYTES = 1024 * 1024


def validate_draft_id(value: str) -> str:
    try:
        if not isinstance(value, str) or str(UUID(value)) != value:
            raise ValueError
    except (ValueError, TypeError, AttributeError):
        raise ValidationError("Draft identity must be a canonical UUID.") from None

    return value


@dataclass(frozen=True, repr=False)
class LocalDraft:
    draft_id: str
    note_id: str | None
    client_operation_id: str
    base_version: int
    revision: int
    title: str
    content: str
    priority: Priority
    category_id: str | None
    updated_at: datetime
    source_locked: bool = False

    def __post_init__(self) -> None:
        validate_draft_id(self.draft_id)
        validate_draft_id(self.client_operation_id)

        if self.note_id is not None:
            validate_id(self.note_id)

        minimum_version = 0 if self.note_id is None else 1

        if type(self.base_version) is not int or self.base_version < minimum_version:
            raise ValidationError("Draft base version is invalid.")

        if self.note_id is None and self.base_version != 0:
            raise ValidationError("A new-note draft must have base version zero.")

        if type(self.revision) is not int or self.revision < 1:
            raise ValidationError("Draft revision must be a positive integer.")

        # Keep incomplete titles exactly as typed; remote validation happens on Save.
        for text in (self.title, self.content):
            if not isinstance(text, str):
                raise ValidationError("Draft text must be strings.")

            try:
                if len(text.encode("utf-8")) > MAX_DRAFT_PAYLOAD_BYTES:
                    raise ValueError
            except (ValueError, UnicodeError):
                raise ValidationError("Draft text exceeds the secure payload bound.") from None

        object.__setattr__(self, "priority", validate_priority(self.priority))
        object.__setattr__(self, "updated_at", utc_datetime(self.updated_at))

        if self.category_id is not None:
            validate_id(self.category_id)

        if type(self.source_locked) is not bool:
            raise ValidationError("Draft lock marker must be a boolean.")


@dataclass(frozen=True)
class DraftHeader:
    draft_id: str


@dataclass(frozen=True)
class DraftAck:
    draft_id: str
    revision: int


class RecoveryKind(str, Enum):
    SAFE_NEW = "SAFE_NEW"
    SAFE_EXISTING = "SAFE_EXISTING"
    REMOTE_CONFLICT = "REMOTE_CONFLICT"
    REMOTE_UNAVAILABLE = "REMOTE_UNAVAILABLE"
    REMOTE_MISSING = "REMOTE_MISSING"
    CORRUPT = "CORRUPT"
    KEY_UNAVAILABLE = "KEY_UNAVAILABLE"
    MISSING = "MISSING"
    LOCKED_UNSUPPORTED = "LOCKED_UNSUPPORTED"


@dataclass(frozen=True)
class RecoveryDecision:
    kind: RecoveryKind
    draft: LocalDraft | None = field(default=None, repr=False)
    remote: NoteView | None = field(default=None, repr=False)
