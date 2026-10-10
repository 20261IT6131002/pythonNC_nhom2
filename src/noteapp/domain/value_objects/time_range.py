"""Pure calendar-day conversion with fold/gap detection."""

from datetime import date, datetime, time, timedelta, timezone, tzinfo

from noteapp.domain.errors import ValidationError


def local_midnight(day: date, zone: tzinfo) -> datetime:
    wall = datetime.combine(day, time.min)
    instants = set()
    for fold in (0, 1):
        candidate = wall.replace(tzinfo=zone, fold=fold).astimezone(timezone.utc)
        if candidate.astimezone(zone).replace(tzinfo=None) == wall:
            instants.add(candidate)
    if len(instants) != 1:
        raise ValidationError("Local midnight is ambiguous or nonexistent.")
    return instants.pop()


def local_date_bounds(
    start: date | None, end: date | None, zone: tzinfo | None
) -> tuple[datetime | None, datetime | None]:
    if any(value is not None and type(value) is not date for value in (start, end)):
        raise ValidationError("Date bounds must be calendar dates.")
    if start is not None and end is not None and start > end:
        raise ValidationError("Start date must not follow end date.")
    if start is None and end is None:
        return None, None
    if zone is None:
        raise ValidationError("Configure a valid IANA timezone for date filters.")
    try:
        lower = local_midnight(start, zone) if start is not None else None
        upper = local_midnight(end + timedelta(days=1), zone) if end is not None else None
    except (OverflowError, ValueError, TypeError):
        raise ValidationError("Date bounds cannot be converted safely.") from None
    return lower, upper
