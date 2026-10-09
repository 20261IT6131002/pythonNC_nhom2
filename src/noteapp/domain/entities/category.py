"""Normalized category model; uniqueness is enforced by the repository."""

import re
from dataclasses import dataclass
from datetime import datetime

from noteapp.domain.errors import ValidationError
from noteapp.domain.policies.note_validation import utc_datetime, validate_id


@dataclass(frozen=True)
class Category:
    id: str
    name: str
    color_hex: str
    created_at: datetime

    def __post_init__(self) -> None:
        validate_id(self.id)
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValidationError("Category name cannot be blank.")
        object.__setattr__(self, "name", self.name.strip())
        if not isinstance(self.color_hex, str) or not re.fullmatch(
            r"#[0-9a-fA-F]{6}", self.color_hex
        ):
            raise ValidationError("Category color must be a six-digit hex color.")
        object.__setattr__(self, "created_at", utc_datetime(self.created_at))

    @property
    def name_key(self) -> str:
        return self.name.casefold()
