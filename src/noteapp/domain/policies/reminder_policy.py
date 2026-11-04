"""Reminder time rules: local wall-clock to UTC without guessing around DST."""

from datetime import datetime, timedelta, timezone, tzinfo

from noteapp.domain.errors import ValidationError

MAX_DELIVERY_ATTEMPTS = 3
RETRY_BACKOFF = (timedelta(minutes=1), timedelta(minutes=5))
CLAIM_LEASE = timedelta(minutes=2)
NOTIFICATION_TITLE_MAX = 120


def retry_delay(attempts: int) -> timedelta:
    """Delay before the next attempt after `attempts` claims have already been made."""
    return RETRY_BACKOFF[min(max(attempts, 1), len(RETRY_BACKOFF)) - 1]


def local_to_utc(value: datetime, zone: tzinfo | None) -> datetime:
    """Interpret a naive wall-clock time in `zone`; reject DST gaps and repeats.

    Aware values are converted as-is. A missing zone is an error: the offset is never guessed.
    """
    if not isinstance(value, datetime):
        raise ValidationError("Reminder time must be a date and time.")
    if value.tzinfo is not None and value.utcoffset() is not None:
        return value.astimezone(timezone.utc)
    if zone is None:
        raise ValidationError("The local timezone could not be determined.")
    first = value.replace(tzinfo=zone, fold=0)
    utc = first.astimezone(timezone.utc)
    if utc.astimezone(zone).replace(tzinfo=None) != value:  # skipped by a spring-forward gap
        raise ValidationError("That local time does not exist because of a DST change.")
    if first.utcoffset() != value.replace(tzinfo=zone, fold=1).utcoffset():  # fall-back repeat
        raise ValidationError("That local time is ambiguous because of a DST change.")
    return utc
