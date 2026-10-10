"""Bounded recent note pages and the seeded category catalog."""

from noteapp.application.dto.note_filter import ListNotesInput
from noteapp.application.dto.note_view import CategoryView, NoteListView, NoteView
from noteapp.application.ports.category_repository import CategoryRepository
from noteapp.application.ports.note_repository import NoteRepository
from noteapp.domain.errors import ValidationError


class ListNotes:
    def __init__(self, notes: NoteRepository) -> None:
        self.notes = notes

    def execute(self, criteria: ListNotesInput | None = None) -> NoteListView:
        criteria = criteria if criteria is not None else ListNotesInput()
        if type(criteria.limit) is not int or not 1 <= criteria.limit <= 100:
            raise ValidationError("Page size must be between 1 and 100.")
        if criteria.cursor is not None and not isinstance(criteria.cursor, str):
            raise ValidationError("Cursor must be a string.")
        page = self.notes.list_recent(criteria.limit, criteria.cursor)
        return NoteListView(
            tuple(NoteView.from_note(note) for note in page.items), page.next_cursor
        )


class ListCategories:
    def __init__(self, categories: CategoryRepository) -> None:
        self.categories = categories

    def execute(self) -> tuple[CategoryView, ...]:
        return tuple(
            CategoryView.from_category(category) for category in self.categories.list_all()
        )
