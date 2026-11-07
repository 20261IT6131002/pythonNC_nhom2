"""Safe worker result envelope: never expose raw exception text."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Generic, TypeVar

from noteapp.domain.errors import (
    AuthenticationFailed,
    CategoryInUse,
    Conflict,
    CorruptedImage,
    DuplicateCategory,
    ExportFailure,
    ExportLocked,
    ImageTooLarge,
    NotFound,
    RepositoryUnavailable,
    SecureStorageUnavailable,
    UnsupportedImage,
    ValidationError,
)

T = TypeVar("T")


class ErrorCode(str, Enum):
    AUTHENTICATION_FAILED = "AUTHENTICATION_FAILED"
    SECURE_STORAGE_UNAVAILABLE = "SECURE_STORAGE_UNAVAILABLE"
    VALIDATION = "VALIDATION"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    UNAVAILABLE = "UNAVAILABLE"
    BUSY = "BUSY"
    DUPLICATE = "DUPLICATE"
    IN_USE = "IN_USE"
    EXPORT_FAILED = "EXPORT_FAILED"
    EXPORT_LOCKED = "EXPORT_LOCKED"
    UNSUPPORTED_IMAGE = "UNSUPPORTED_IMAGE"
    IMAGE_TOO_LARGE = "IMAGE_TOO_LARGE"
    IMAGE_CORRUPT = "IMAGE_CORRUPT"
    UNEXPECTED = "UNEXPECTED"


@dataclass(frozen=True)
class OperationResult(Generic[T]):
    value: T | None = field(default=None, repr=False)
    error: ErrorCode | None = None

    @property
    def ok(self) -> bool:
        return self.error is None

    @classmethod
    def failed(cls, error: Exception) -> "OperationResult":
        mapping = (
            (AuthenticationFailed, ErrorCode.AUTHENTICATION_FAILED),
            (SecureStorageUnavailable, ErrorCode.SECURE_STORAGE_UNAVAILABLE),
            (ValidationError, ErrorCode.VALIDATION),
            (NotFound, ErrorCode.NOT_FOUND),
            (Conflict, ErrorCode.CONFLICT),
            (ExportFailure, ErrorCode.EXPORT_FAILED),
            (ExportLocked, ErrorCode.EXPORT_LOCKED),
            (RepositoryUnavailable, ErrorCode.UNAVAILABLE),
            (DuplicateCategory, ErrorCode.DUPLICATE),
            (CategoryInUse, ErrorCode.IN_USE),
            (UnsupportedImage, ErrorCode.UNSUPPORTED_IMAGE),
            (ImageTooLarge, ErrorCode.IMAGE_TOO_LARGE),
            (CorruptedImage, ErrorCode.IMAGE_CORRUPT),
        )
        code = next(
            (code for kind, code in mapping if isinstance(error, kind)), ErrorCode.UNEXPECTED
        )
        return cls(error=code)
