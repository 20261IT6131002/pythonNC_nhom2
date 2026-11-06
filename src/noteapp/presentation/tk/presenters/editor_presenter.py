"""Snapshot save requests and retain edits made while Mongo is working."""

from collections.abc import Callable
from dataclasses import replace
from datetime import datetime
from functools import partial
from uuid import uuid4

from noteapp.application.commands.create import CreateNote
from noteapp.application.commands.update import UpdateNote
from noteapp.application.dto.local_draft import DraftAck, RecoveryDecision, RecoveryKind
from noteapp.application.dto.note_input import CreateNoteInput, Priority, UpdateNoteInput
from noteapp.application.dto.note_view import NoteView
from noteapp.application.dto.operation_result import ErrorCode, OperationResult
from noteapp.presentation.tk.async_bridge.task_runner import TaskEvent, TaskRunner
from noteapp.presentation.tk.state.editor_state import EditorPhase, EditorState
from noteapp.presentation.tk.state.sync_state import SyncState


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
        self.on_ack: Callable[[DraftAck], None] | None = None
        self._saving_draft_revision = 0

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
            attachment=note.attachment,
            reminder=note.reminder,
            is_pinned=note.is_pinned,
        )
        self._pending = None
        self.on_change(self.state, True)

    def recover(self, decision: RecoveryDecision) -> None:
        draft = decision.draft

        if draft is None or draft.source_locked:
            return

        remote = decision.remote
        conflict = decision.kind in {RecoveryKind.REMOTE_CONFLICT, RecoveryKind.REMOTE_MISSING}
        self.state = EditorState(
            note_id=draft.note_id,
            title=draft.title,
            content=draft.content,
            priority=draft.priority,
            category_id=draft.category_id,
            version=draft.base_version,
            revision=draft.revision,
            operation_id=draft.client_operation_id,
            draft_id=draft.draft_id,
            draft_revision=draft.revision,
            phase=EditorPhase.CONFLICT if conflict else EditorPhase.DIRTY,
            error=ErrorCode.CONFLICT if conflict else None,
            sync=SyncState.LOCAL_SAVED,
            updated_at=remote.updated_at if remote else None,
            attachment=remote.attachment if remote else None,
            reminder=remote.reminder if remote else None,
            is_pinned=remote.is_pinned if remote else False,
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

    def apply_pinned(self, saved: NoteView) -> None:
        """Adopt pin metadata and CAS version without replacing unsaved text or revision."""
        state = self.state
        if state.note_id != saved.note_id or saved.version < state.version:
            return

        state.version = saved.version
        state.is_pinned = saved.is_pinned
        self.on_change(state, False)

    def apply_attachment(self, saved: NoteView) -> None:
        """Adopt the new version/image after an image change without touching text edits."""
        state = self.state
        if state.note_id != saved.note_id:
            return
        state.version, state.updated_at = saved.version, saved.updated_at
        state.attachment = saved.attachment
        self.on_change(state, False)

    def apply_reminder(self, saved: NoteView) -> None:
        """Adopt the new version/reminder after a reminder change; text edits are kept."""
        state = self.state
        if state.note_id != saved.note_id:
            return
        state.version, state.updated_at = saved.version, saved.updated_at
        state.reminder = saved.reminder
        self.on_change(state, False)

    def apply_delivered(self, delivered_at_by_note: dict[str, datetime]) -> bool:
        """Show delivery of the open note's reminder; delivery never changes the version."""
        state = self.state
        at = delivered_at_by_note.get(state.note_id)
        if at is None or state.reminder is None or state.reminder.status != "ACTIVE":
            return False
        state.reminder = replace(state.reminder, status="DELIVERED", delivered_at=at)
        self.on_change(state, False)
        return True

    @property
    def saving(self) -> bool:
        return self._pending is not None

    def save(self) -> bool:
        if not self._alive or self._pending is not None:
            return False
        state = self.state
        if state.source_locked:
            state.error = ErrorCode.VALIDATION
            self.on_change(state, False)
            return False

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
        self._saving_draft_revision = state.draft_revision
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
            if state.error == ErrorCode.UNAVAILABLE and state.sync != SyncState.LOCAL_SAVED:
                state.sync = SyncState.OFFLINE

            state.phase = (
                EditorPhase.CONFLICT if state.error == ErrorCode.CONFLICT else EditorPhase.ERROR
            )
            self.on_change(state, False)
            return
        saved = event.result.value
        state.is_pinned = saved.is_pinned
        state.note_id, state.version = saved.note_id, saved.version
        state.updated_at = saved.updated_at
        state.attachment = saved.attachment
        state.reminder = saved.reminder
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
            if self.on_ack is not None and self._saving_draft_revision > 0:
                self.on_ack(DraftAck(state.draft_id, self._saving_draft_revision))
            self.on_change(state, True)
        else:
            state.phase = EditorPhase.DIRTY
            self.on_change(state, False)
        self.on_saved()

    def close(self) -> None:
        self._alive = False
        self._pending = None
