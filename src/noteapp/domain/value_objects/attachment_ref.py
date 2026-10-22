"""Attachment reference value object: opaque key, no storage-driver types."""

import re
from dataclasses import dataclass
from enum import Enum

from noteapp.domain.errors import ValidationError
from noteapp.domain.policies.attachment_policy import (
    sanitize_display_name,
    storage_kind_for,
    validate_mime_type,
)


class StorageKind(str, Enum):
    INLINE = "INLINE"
    GRIDFS = "GRIDFS"


@dataclass(frozen=True)
class AttachmentRef:
    storage_kind: StorageKind
    storage_key: str
    mime_type: str
    size_bytes: int
    sha256: str
    display_name: str

    def __post_init__(self) -> None:
        try:
            kind = StorageKind(self.storage_kind)
        except ValueError as error:
            raise ValidationError("Unknown attachment storage kind.") from error
        object.__setattr__(self, "storage_kind", kind)
        if (
            not isinstance(self.storage_key, str)
            or not 1 <= len(self.storage_key) <= 64
            or not self.storage_key.isascii()
            or not self.storage_key.isprintable()
            or " " in self.storage_key
        ):
            raise ValidationError("Attachment storage key must be a short opaque string.")
        validate_mime_type(self.mime_type)
        if storage_kind_for(self.size_bytes) != kind.value:
            raise ValidationError("Attachment storage kind does not match its size.")
        if not isinstance(self.sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", self.sha256):
            raise ValidationError("Attachment hash must be a lowercase SHA-256 hex digest.")
        object.__setattr__(self, "display_name", sanitize_display_name(self.display_name))
