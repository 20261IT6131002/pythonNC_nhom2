"""FR-02: safe optimistic updates without silent overwrite."""

from noteapp.application.dto.note_input import UpdateNoteInput
from noteapp.application.dto.note_view import NoteView
from noteapp.application.ports.category_repository import CategoryRepository
from noteapp.application.ports.clock import Clock
from noteapp.application.ports.note_repository import NoteRepository
from noteapp.domain.errors import Conflict, NotFound, ValidationError
from noteapp.domain.policies.note_validation import validate_id, validate_version


class UpdateNote:
    def __init__(self, notes: NoteRepository, categories: CategoryRepository, clock: Clock) -> None:
        self.notes, self.categories, self.clock = notes, categories, clock

    def execute(self, command: UpdateNoteInput) -> NoteView:
        validate_id(command.note_id)
        validate_version(command.expected_version)
        current = self.notes.find_by_id(command.note_id)
        if current is None:
            raise NotFound("Note not found.")
        if current.version != command.expected_version:
            raise Conflict("The note has been changed by another editor.")
        updated = current.edited(
            title=command.title,
            content=command.content,
            priority=command.priority,
            category_id=command.category_id,
            now=self.clock.now(),
        )
        if (
            updated.category_id is not None
            and self.categories.find_by_id(updated.category_id) is None
        ):
            raise ValidationError("The selected category does not exist.")
        if not self.notes.update_if_version(updated, command.expected_version):
            if self.notes.find_by_id(command.note_id) is None:
                raise NotFound("Note not found.")
            raise Conflict("The note has been changed by another editor.")
        return NoteView.from_note(updated)
