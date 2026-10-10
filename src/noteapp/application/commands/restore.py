"""Restore same ID and payload through an atomic versioned port."""

from noteapp.application.dto.note_input import RestoreNoteInput
from noteapp.application.dto.note_view import NoteView
from noteapp.application.ports.clock import Clock
from noteapp.application.ports.trash_repository import TrashRepository
from noteapp.domain.errors import ValidationError
from noteapp.domain.policies.note_validation import utc_datetime, validate_id, validate_version


class RestoreNote:
    def __init__(self, repo: TrashRepository, clock: Clock) -> None:
        self.repo, self.clock = repo, clock

    def execute(self, command: RestoreNoteInput) -> NoteView:
        if not isinstance(command, RestoreNoteInput):
            raise ValidationError("Restore requires typed input.")
        validate_id(command.note_id)
        validate_version(command.expected_version)
        note = self.repo.restore(
            command.note_id, command.expected_version, utc_datetime(self.clock.now())
        )
        return NoteView.from_note(note)
