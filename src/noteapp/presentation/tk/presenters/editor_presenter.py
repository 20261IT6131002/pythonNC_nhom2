"""Snapshot save requests and retain edits made while Mongo is working."""

from collections.abc import Callable
from functools import partial
from uuid import uuid4

from noteapp.application.commands.create import CreateNote
from noteapp.application.commands.update import UpdateNote
from noteapp.application.dto.note_input import CreateNoteInput, Priority, UpdateNoteInput
from noteapp.application.dto.note_view import NoteView
from noteapp.application.dto.operation_result import ErrorCode, OperationResult
from noteapp.presentation.tk.async_bridge.task_runner import TaskEvent, TaskRunner
from noteapp.presentation.tk.state.editor_state import EditorPhase, EditorState


class EditorPresenter:
    def __init__(
        self,
        create: CreateNote,
        update: UpdateNote,
        runner: TaskRunner,
        on_change: Callable[[EditorState, bool], None],
        on_saved: Callable[[], None],
    ) -> None:
        self.create, self.update, self.runner = create, update, runner
        self.on_change, self.on_saved = on_change, on_saved
        self.state = EditorState()
        self._pending: str | None = None
        self._saving_revision = 0
        self._alive = True

    def new(self) -> None:
        self.state = EditorState()
        self._pending = None
        self.on_change(self.state, True)

    def open(self, note: NoteView) -> None:
        self.state = EditorState(
            note_id=note.note_id,
            title=note.title,
            content=note.content,
            priority=note.priority,
            category_id=note.category_id,
            version=note.version,
            updated_at=note.updated_at,
        )
        self._pending = None
        self.on_change(self.state, True)

    def edit(self, title: str, content: str, priority: Priority, category_id: str | None) -> None:
        state = self.state
        if (title, content, priority, category_id) == (
            state.title,
            state.content,
            state.priority,
            state.category_id,
        ):
            return
        state.title, state.content = title, content
        state.priority, state.category_id = priority, category_id
        state.revision += 1
        if self._pending is None:
            state.phase = EditorPhase.DIRTY
        state.error = None
        self.on_change(state, False)

    def save(self) -> bool:
        if not self._alive or self._pending is not None:
            return False
        state = self.state
        request_id = "save:" + uuid4().hex
        if state.note_id is None:
            command = CreateNoteInput(
                state.title, state.content, state.priority, state.category_id, state.operation_id
            )
            task = partial(self.create.execute, command)
        else:
            command = UpdateNoteInput(
                state.note_id,
                state.title,
                state.content,
                state.priority,
                state.category_id,
                state.version,
            )
            task = partial(self.update.execute, command)
        self._pending = request_id
        self._saving_revision = state.revision
        state.phase, state.error = EditorPhase.SAVING, None
        self.on_change(state, False)
        if not self.runner.submit(request_id, "save", task):
            self.handle(TaskEvent(request_id, "save", OperationResult(error=ErrorCode.BUSY)))
            return False
        return True

    def handle(self, event: TaskEvent) -> None:
        if not self._alive or event.operation != "save" or event.request_id != self._pending:
            return
        self._pending = None
        state = self.state
        if not event.result.ok:
            state.error = event.result.error
            state.phase = (
                EditorPhase.CONFLICT if state.error == ErrorCode.CONFLICT else EditorPhase.ERROR
            )
            self.on_change(state, False)
            return
        saved = event.result.value
        state.note_id, state.version = saved.note_id, saved.version
        state.updated_at = saved.updated_at
        same_payload = (state.title.strip(), state.content, state.priority, state.category_id) == (
            saved.title,
            saved.content,
            saved.priority,
            saved.category_id,
        )
        if state.revision == self._saving_revision and same_payload:
            state.title, state.content = saved.title, saved.content
            state.priority, state.category_id = saved.priority, saved.category_id
            state.phase = EditorPhase.SAVED
            self.on_change(state, True)
        else:
            state.phase = EditorPhase.DIRTY
            self.on_change(state, False)
        self.on_saved()

    def close(self) -> None:
        self._alive = False
        self._pending = None
