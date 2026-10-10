"""Fetch an active note for the editor."""

from noteapp.application.dto.note_view import NoteView
from noteapp.application.ports.note_repository import NoteRepository
from noteapp.domain.errors import NotFound
from noteapp.domain.policies.note_validation import validate_id


class GetNote:
    def __init__(self, notes: NoteRepository) -> None:
        self.notes = notes

    def execute(self, note_id: str) -> NoteView:
        note = self.notes.find_by_id(validate_id(note_id))
        if note is None:
            raise NotFound("Note not found.")
        return NoteView.from_note(note)
