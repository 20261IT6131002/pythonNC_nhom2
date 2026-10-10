"""Safe worker result envelope: never expose raw exception text."""

from dataclasses import dataclass
from enum import Enum
from typing import Generic, TypeVar

from noteapp.domain.errors import (
    Conflict,
    DuplicateCategory,
    NotFound,
    RepositoryUnavailable,
    ValidationError,
)

T = TypeVar("T")


class ErrorCode(str, Enum):
    VALIDATION = "VALIDATION"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    UNAVAILABLE = "UNAVAILABLE"
    BUSY = "BUSY"
    UNEXPECTED = "UNEXPECTED"


@dataclass(frozen=True)
class OperationResult(Generic[T]):
    value: T | None = None
    error: ErrorCode | None = None

    @property
    def ok(self) -> bool:
        return self.error is None

    @classmethod
    def failed(cls, error: Exception) -> "OperationResult":
        mapping = (
            (ValidationError, ErrorCode.VALIDATION),
            (NotFound, ErrorCode.NOT_FOUND),
            (Conflict, ErrorCode.CONFLICT),
            (RepositoryUnavailable, ErrorCode.UNAVAILABLE),
            (DuplicateCategory, ErrorCode.VALIDATION),
        )
        code = next(
            (code for kind, code in mapping if isinstance(error, kind)), ErrorCode.UNEXPECTED
        )
        return cls(error=code)
