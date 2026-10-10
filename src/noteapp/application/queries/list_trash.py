"""Typed bounded trash pages independent of active lists."""

from noteapp.application.dto.note_input import ListTrashInput
from noteapp.application.dto.note_view import NoteView, TrashedNoteView, TrashListView
from noteapp.application.ports.trash_repository import TrashRepository
from noteapp.domain.errors import ValidationError


class ListTrash:
    def __init__(self, repo: TrashRepository) -> None:
        self.repo = repo

    def execute(self, command: ListTrashInput | None = None) -> TrashListView:
        command = command if command is not None else ListTrashInput()
        if not isinstance(command, ListTrashInput):
            raise ValidationError("Trash list requires typed input.")
        if type(command.limit) is not int or not 1 <= command.limit <= 100:
            raise ValidationError("Page size must be between 1 and 100.")
        if command.cursor is not None and (
            not isinstance(command.cursor, str) or not command.cursor or len(command.cursor) > 2048
        ):
            raise ValidationError("Invalid trash cursor.")
        page = self.repo.list_trashed(command.limit, command.cursor)
        return TrashListView(
            tuple(
                TrashedNoteView(NoteView.from_note(row.note), row.deleted_at) for row in page.items
            ),
            page.next_cursor,
        )
