"""Immutable text note without UI or BSON dependencies."""

from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import ClassVar

from noteapp.domain.entities.reminder import Reminder
from noteapp.domain.errors import ValidationError
from noteapp.domain.policies.note_validation import (
    utc_datetime,
    validate_content,
    validate_id,
    validate_priority,
    validate_title,
    validate_version,
)
from noteapp.domain.value_objects.attachment_ref import AttachmentRef
from noteapp.domain.value_objects.priority import Priority


@dataclass(frozen=True)
class Note:
    id: str
    title: str = field(repr=False)
    content: str | None = field(repr=False)
    priority: Priority
    category_id: str | None
    version: int
    created_at: datetime
    updated_at: datetime
    attachment: AttachmentRef | None = None
    reminder: Reminder | None = None
    is_pinned: bool = False

    is_locked: ClassVar[bool] = False

    def __post_init__(self) -> None:
        if type(self.is_pinned) is not bool:
            raise ValidationError("Pinned state must be a boolean.")
        validate_id(self.id)
        object.__setattr__(self, "title", validate_title(self.title))
        if not self.is_locked:
            validate_content(self.content)
        object.__setattr__(self, "priority", validate_priority(self.priority))
        if self.category_id is not None:
            validate_id(self.category_id)
        validate_version(self.version)
        object.__setattr__(self, "created_at", utc_datetime(self.created_at))
        object.__setattr__(self, "updated_at", utc_datetime(self.updated_at))
        if self.updated_at < self.created_at:
            raise ValidationError("Update time cannot precede creation time.")
        if self.attachment is not None and not isinstance(self.attachment, AttachmentRef):
            raise ValidationError("Attachment must be an attachment reference.")
        if self.reminder is not None and not isinstance(self.reminder, Reminder):
            raise ValidationError("Reminder must be a reminder value.")

    def with_pinned(self, target: bool) -> "Note":
        """Change ordering metadata without changing the content modification time."""
        if type(target) is not bool:
            raise ValidationError("Pinned state must be a boolean.")
        if target == self.is_pinned:
            return self
        return replace(self, is_pinned=target, version=self.version + 1)

    def edited(
        self,
        *,
        title: str,
        content: str,
        priority: Priority,
        category_id: str | None,
        now: datetime,
    ) -> "Note":
        if self.is_locked:
            raise ValidationError("Use the authenticated editor for a locked note.")
        return replace(
            self,
            title=title,
            content=content,
            priority=priority,
            category_id=category_id,
            version=self.version + 1,
            updated_at=max(utc_datetime(now), self.updated_at),
        )

    def with_attachment(self, attachment: AttachmentRef | None, now: datetime) -> "Note":
        """Return the next version with a new (or removed) image; text is untouched."""
        return replace(
            self,
            attachment=attachment,
            version=self.version + 1,
            updated_at=max(utc_datetime(now), self.updated_at),
        )

    def with_reminder(self, reminder: Reminder | None, now: datetime) -> "Note":
        """Return the next version with the reminder changed; text and image are untouched."""
        return replace(
            self,
            reminder=reminder,
            version=self.version + 1,
            updated_at=max(utc_datetime(now), self.updated_at),
        )


LOCKED_TITLE = "Ghi chú đã khóa"


@dataclass(frozen=True)
class LockedNote(Note):
    """Safe metadata for a locked record. The encrypted payload is read separately."""

    title: str = field(init=False, default=LOCKED_TITLE)
    content: None = field(init=False, default=None, repr=False)
    is_locked: ClassVar[bool] = True
