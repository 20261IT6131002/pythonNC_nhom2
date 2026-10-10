"""Ignore stale list responses; concatenate only one requested page."""

from collections.abc import Callable
from dataclasses import replace
from functools import partial
from uuid import uuid4

from noteapp.application.dto.note_filter import ListNotesInput, SearchNotesCriteria
from noteapp.application.dto.note_input import ListTrashInput
from noteapp.application.dto.note_view import NoteListView
from noteapp.application.dto.operation_result import ErrorCode, OperationResult
from noteapp.application.queries.list_notes import ListNotes
from noteapp.application.queries.list_trash import ListTrash
from noteapp.application.queries.search_notes import SearchNotes
from noteapp.presentation.tk.async_bridge.task_runner import TaskEvent, TaskRunner
from noteapp.presentation.tk.state.list_state import ListState


class NotesPresenter:
    def __init__(
        self,
        query: ListNotes | SearchNotes | ListTrash,
        runner: TaskRunner,
        on_change: Callable[[ListState], None],
    ) -> None:
        self.query, self.runner, self.on_change = query, runner, on_change
        self.state = ListState()
        self._pending = None
        self._append = False
        self._alive = True
        self.criteria = (
            SearchNotesCriteria() if isinstance(query, SearchNotes) else ListNotesInput()
        )

    def configure(
        self,
        query: ListNotes | SearchNotes | ListTrash,
        criteria: SearchNotesCriteria | ListNotesInput | ListTrashInput,
        mode: str = "active",
    ) -> None:
        self.query, self.criteria = query, replace(criteria, cursor=None)
        self._pending = None
        self._append = False
        self.state = ListState(mode=mode, generation=self.state.generation + 1)
        self.on_change(self.state)

    def invalidate(self) -> None:
        self._pending = None
        self.state = ListState(mode=self.state.mode, generation=self.state.generation + 1)
        self.on_change(self.state)

    def invalid_input(self) -> None:
        self.invalidate()
        self.state.error = ErrorCode.VALIDATION
        self.on_change(self.state)

    def refresh(self, append: bool = False) -> None:
        if not self._alive or (append and (self.state.loading or self.state.next_cursor is None)):
            return
        request_id = "list:" + uuid4().hex
        self._pending, self._append = request_id, append
        criteria = replace(self.criteria, cursor=self.state.next_cursor if append else None)
        self.state.loading, self.state.error = True, None
        self.on_change(self.state)
        if not self.runner.submit(request_id, "list", partial(self.query.execute, criteria)):
            self.handle(TaskEvent(request_id, "list", OperationResult(error=ErrorCode.BUSY)))

    def handle(self, event: TaskEvent) -> None:
        if not self._alive or event.operation != "list" or event.request_id != self._pending:
            return
        self._pending = None
        self.state.loading = False
        if not event.result.ok:
            self.state.error = event.result.error
        else:
            page = event.result.value
            if self.state.mode == "trash":
                self.state.trash_items = (
                    self.state.trash_items + page.items if self._append else page.items
                )
                page = NoteListView(tuple(row.note for row in page.items), page.next_cursor)
            if self._append:
                existing = {item.note_id for item in self.state.items}
                self.state.items += tuple(
                    item for item in page.items if item.note_id not in existing
                )
            else:
                self.state.items = page.items
            self.state.next_cursor, self.state.error = page.next_cursor, None
        self.on_change(self.state)

    def close(self) -> None:
        self._alive = False
        self._pending = None
