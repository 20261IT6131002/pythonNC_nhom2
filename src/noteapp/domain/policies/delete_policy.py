"""Pure transition/version rules and UTC retention eligibility."""

from dataclasses import replace
from datetime import datetime, timedelta

from noteapp.domain.entities.note import Note
from noteapp.domain.errors import Conflict, ValidationError
from noteapp.domain.policies.note_validation import utc_datetime, validate_version


def transition_note(
    note: Note, expected_version: int, is_deleted: bool, target_deleted: bool, now: datetime
) -> Note:
    validate_version(expected_version)
    if type(is_deleted) is not bool or type(target_deleted) is not bool:
        raise ValidationError("Invalid deletion state.")
    if note.version != expected_version or is_deleted == target_deleted:
        raise Conflict("The note state or version has changed.")
    return replace(
        note, version=note.version + 1, updated_at=max(utc_datetime(now), note.updated_at)
    )


def retention_cutoff(now: datetime) -> datetime:
    return utc_datetime(now) - timedelta(days=30)
