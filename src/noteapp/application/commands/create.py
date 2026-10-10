"""FR-01: validate and create one logical note per operation ID."""

from secrets import token_hex
from uuid import UUID

from noteapp.application.dto.note_input import CreateNoteInput
from noteapp.application.dto.note_view import NoteView
from noteapp.application.ports.category_repository import CategoryRepository
from noteapp.application.ports.clock import Clock
from noteapp.application.ports.note_repository import NoteRepository
from noteapp.domain.entities.note import Note
from noteapp.domain.errors import ValidationError


class CreateNote:
    def __init__(self, notes: NoteRepository, categories: CategoryRepository, clock: Clock) -> None:
        self.notes, self.categories, self.clock = notes, categories, clock

    def execute(self, command: CreateNoteInput) -> NoteView:
        try:
            operation_id = str(UUID(command.client_operation_id))
        except (TypeError, ValueError, AttributeError) as error:
            raise ValidationError("Create requires a stable UUID operation ID.") from error
        now = self.clock.now()
        note = Note(
            token_hex(12),
            command.title,
            command.content,
            command.priority,
            command.category_id,
            1,
            now,
            now,
        )
        if note.category_id is not None and self.categories.find_by_id(note.category_id) is None:
            raise ValidationError("The selected category does not exist.")
        return NoteView.from_note(self.notes.create(note, operation_id))
