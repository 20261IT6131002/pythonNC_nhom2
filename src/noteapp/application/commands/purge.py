"""Permanent delete is opt-in even when bypassing GUI confirmation."""

from noteapp.application.dto.note_input import PurgeNoteInput
from noteapp.application.ports.trash_repository import TrashRepository
from noteapp.domain.errors import ValidationError
from noteapp.domain.policies.note_validation import validate_id, validate_version


class PurgeNote:
    def __init__(self, repo: TrashRepository) -> None:
        self.repo = repo

    def execute(self, command: PurgeNoteInput) -> None:
        if not isinstance(command, PurgeNoteInput) or command.confirmed is not True:
            raise ValidationError("Permanent deletion requires explicit confirmation.")
        validate_id(command.note_id)
        validate_version(command.expected_version)
        self.repo.purge_confirmed(command.note_id, command.expected_version)
