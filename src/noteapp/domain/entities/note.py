"""Immutable text note without UI or BSON dependencies."""

from dataclasses import dataclass, replace
from datetime import datetime

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
    title: str
    content: str
    priority: Priority
    category_id: str | None
    version: int
    created_at: datetime
    updated_at: datetime
    attachment: AttachmentRef | None = None
    reminder: Reminder | None = None

    def __post_init__(self) -> None:
        validate_id(self.id)
        object.__setattr__(self, "title", validate_title(self.title))
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

    def edited(
        self,
        *,
        title: str,
        content: str,
        priority: Priority,
        category_id: str | None,
        now: datetime,
    ) -> "Note":
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
