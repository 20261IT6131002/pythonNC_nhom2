"""Run pin mutations in the bounded worker pool; discard unrelated and late results."""

from collections.abc import Callable
from functools import partial
from uuid import uuid4

from noteapp.application.commands.set_pinned import SetPinned
from noteapp.application.dto.note_input import SetPinnedInput
from noteapp.application.dto.note_view import NoteView
from noteapp.application.dto.operation_result import ErrorCode, OperationResult
from noteapp.presentation.tk.async_bridge.task_runner import TaskEvent, TaskRunner

PIN_OPERATION = "set_pinned"


class PinPresenter:
    def __init__(
        self,
        command: SetPinned,
        runner: TaskRunner,
        on_changed: Callable[[NoteView], None],
        on_failed: Callable[[str, ErrorCode], None],
        on_busy: Callable[[bool], None],
    ) -> None:
        self.command = command
        self.runner = runner
        self.on_changed = on_changed
        self.on_failed = on_failed
        self.on_busy = on_busy
        self._pending: tuple[str, str] | None = None
        self._alive = True

    @property
    def busy(self) -> bool:
        return self._pending is not None

    def set(self, note_id: str, version: int, target: bool) -> bool:
        if not self._alive or self.busy:
            return False

        request_id = PIN_OPERATION + ":" + uuid4().hex
        command = SetPinnedInput(note_id, version, target)
        self._pending = (request_id, note_id)
        self.on_busy(True)

        task = partial(self.command.execute, command)
        if not self.runner.submit(request_id, PIN_OPERATION, task):
            self.handle(TaskEvent(request_id, PIN_OPERATION, OperationResult(error=ErrorCode.BUSY)))
            return False

        return True

    def handle(self, event: TaskEvent) -> None:
        if not self._alive or event.operation != PIN_OPERATION:
            return
        if self._pending is None or event.request_id != self._pending[0]:
            return

        _, note_id = self._pending
        self._pending = None
        self.on_busy(False)

        if event.result.ok:
            self.on_changed(event.result.value)
        else:
            self.on_failed(note_id, event.result.error)

    def close(self) -> None:
        self._alive = False
        self._pending = None
