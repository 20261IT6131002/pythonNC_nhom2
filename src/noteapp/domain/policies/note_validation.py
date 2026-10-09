"""Pure validation for the Phase 1 text slice."""

from datetime import datetime, timezone

from noteapp.domain.errors import ValidationError
from noteapp.domain.value_objects.priority import Priority


def validate_title(title: str) -> str:
    if not isinstance(title, str) or not 1 <= len(title.strip()) <= 250:
        raise ValidationError("Title must contain 1 to 250 characters after trimming.")
    return title.strip()


def validate_content(content: str) -> str:
    if not isinstance(content, str):
        raise ValidationError("Content must be text.")
    return content


def validate_priority(priority: Priority) -> Priority:
    try:
        return Priority(priority)
    except (TypeError, ValueError) as error:
        raise ValidationError("Priority must be HIGH, MEDIUM or LOW.") from error


def utc_datetime(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValidationError("Timestamps must be timezone-aware.")
    return value.astimezone(timezone.utc)


def validate_id(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError("A non-empty record ID is required.")
    return value


def validate_version(value: int) -> int:
    if type(value) is not int or value < 1:
        raise ValidationError("Version must be a positive integer.")
    return value
