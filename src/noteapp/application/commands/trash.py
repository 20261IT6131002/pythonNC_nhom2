"""Explicit versioned move to trash; success only after repository ACK."""

from noteapp.application.dto.note_input import TrashNoteInput
from noteapp.application.dto.note_view import NoteView, TrashedNoteView
from noteapp.application.ports.clock import Clock
from noteapp.application.ports.trash_repository import TrashRepository
from noteapp.domain.errors import ValidationError
from noteapp.domain.policies.note_validation import utc_datetime, validate_id, validate_version


class TrashNote:
    def __init__(self, repo: TrashRepository, clock: Clock) -> None:
        self.repo, self.clock = repo, clock

    def execute(self, command: TrashNoteInput) -> TrashedNoteView:
        if not isinstance(command, TrashNoteInput):
            raise ValidationError("Trash requires typed input.")
        validate_id(command.note_id)
        validate_version(command.expected_version)
        record = self.repo.move_to_trash(
            command.note_id, command.expected_version, utc_datetime(self.clock.now())
        )
        return TrashedNoteView(NoteView.from_note(record.note), record.deleted_at)
