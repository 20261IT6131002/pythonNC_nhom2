"""Set/reschedule/cancel in workers; late results for another note are discarded."""

from collections.abc import Callable
from datetime import datetime
from functools import partial
from uuid import uuid4

from noteapp.application.commands.set_reminder import ReminderTools
from noteapp.application.dto.note_input import CancelReminderInput, SetReminderInput
from noteapp.application.dto.note_view import NoteView
from noteapp.application.dto.operation_result import ErrorCode, OperationResult
from noteapp.presentation.tk.async_bridge.task_runner import TaskEvent, TaskRunner

MUTATE = "reminder_change"


class ReminderPresenter:
    def __init__(
        self,
        tools: ReminderTools,
        runner: TaskRunner,
        on_changed: Callable[[NoteView], None],
        on_change_failed: Callable[[ErrorCode], None],
        on_busy: Callable[[bool], None],
    ) -> None:
        self.tools, self.runner = tools, runner
        self.on_changed, self.on_change_failed, self.on_busy = on_changed, on_change_failed, on_busy
        self._change: tuple[str, str] | None = None  # (request_id, note_id)
        self._alive = True

    @property
    def busy(self) -> bool:
        return self._change is not None

    def set(self, note_id: str, version: int, due_at: datetime) -> bool:
        command = SetReminderInput(note_id, version, due_at)
        return self._mutate(note_id, partial(self.tools.set.execute, command))

    def cancel(self, note_id: str, version: int) -> bool:
        command = CancelReminderInput(note_id, version)
        return self._mutate(note_id, partial(self.tools.cancel.execute, command))

    def _mutate(self, note_id: str, task) -> bool:
        if not self._alive or self._change is not None:
            return False
        request_id = MUTATE + ":" + uuid4().hex
        self._change = (request_id, note_id)
        self.on_busy(True)
        if not self.runner.submit(request_id, MUTATE, task):
            self.handle(TaskEvent(request_id, MUTATE, OperationResult(error=ErrorCode.BUSY)))
            return False
        return True

    def handle(self, event: TaskEvent) -> None:
        if not self._alive or event.operation != MUTATE:
            return
        if not self._change or event.request_id != self._change[0]:
            return
        self._change = None
        self.on_busy(False)
        if event.result.ok:
            self.on_changed(event.result.value)
        else:
            self.on_change_failed(event.result.error)

    def close(self) -> None:
        self._alive = False
        self._change = None
