"""Immutable text note without UI or BSON dependencies."""

from dataclasses import dataclass, replace
from datetime import datetime

from noteapp.domain.errors import ValidationError
from noteapp.domain.policies.note_validation import (
    utc_datetime,
    validate_content,
    validate_id,
    validate_priority,
    validate_title,
    validate_version,
)
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
