"""FR-12: explicit pin intent, active-only CAS and idempotent same-target requests."""

from noteapp.application.dto.note_input import SetPinnedInput
from noteapp.application.dto.note_view import NoteView
from noteapp.application.ports.note_repository import NoteRepository
from noteapp.domain.errors import Conflict, NotFound, ValidationError
from noteapp.domain.policies.note_validation import validate_id, validate_version


class SetPinned:
    def __init__(self, notes: NoteRepository) -> None:
        self.notes = notes

    def execute(self, command: SetPinnedInput) -> NoteView:
        validate_id(command.note_id)
        validate_version(command.expected_version)

        if type(command.target) is not bool:
            raise ValidationError("Pinned state must be a boolean.")

        current = self.notes.find_by_id(command.note_id)
        if current is None:
            raise NotFound("Note not found.")

        if current.version != command.expected_version:
            raise Conflict("The note has been changed by another editor.")

        updated = current.with_pinned(command.target)
        if updated is current:
            return NoteView.from_note(current)

        if not self.notes.set_pinned_if_version(updated, current.version):
            if self.notes.find_by_id(current.id) is None:
                raise NotFound("Note not found.")

            raise Conflict("The note has been changed by another editor.")

        return NoteView.from_note(updated)
