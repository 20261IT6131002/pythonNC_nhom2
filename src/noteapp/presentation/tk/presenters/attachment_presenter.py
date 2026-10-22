"""Image attach/remove/preview in workers; late or stale results are discarded."""

from collections.abc import Callable
from functools import partial
from uuid import uuid4

from noteapp.application.dto.note_input import (
    AttachImageFileInput,
    GetImageInput,
    RemoveImageInput,
)
from noteapp.application.dto.note_view import ImageContent, NoteView
from noteapp.application.dto.operation_result import ErrorCode, OperationResult
from noteapp.application.services.attachment_service import AttachmentService
from noteapp.presentation.tk.async_bridge.task_runner import TaskEvent, TaskRunner

MUTATE = "image_change"
LOAD = "image_load"


class AttachmentPresenter:
    def __init__(
        self,
        service: AttachmentService,
        runner: TaskRunner,
        on_changed: Callable[[NoteView], None],
        on_change_failed: Callable[[ErrorCode], None],
        on_loaded: Callable[[str, ImageContent], None],
        on_load_failed: Callable[[str, ErrorCode], None],
        on_busy: Callable[[bool], None],
    ) -> None:
        self.service, self.runner = service, runner
        self.on_changed, self.on_change_failed = on_changed, on_change_failed
        self.on_loaded, self.on_load_failed, self.on_busy = on_loaded, on_load_failed, on_busy
        self._change: tuple[str, str] | None = None  # (request_id, note_id)
        self._load: tuple[str, str] | None = None
        self._alive = True

    @property
    def busy(self) -> bool:
        return self._change is not None

    @property
    def loading_note_id(self) -> str | None:
        return self._load[1] if self._load else None

    def attach(self, note_id: str, version: int, path: str) -> bool:
        command = AttachImageFileInput(note_id, version, path)
        return self._mutate(note_id, partial(self.service.attach_from_file, command))

    def remove(self, note_id: str, version: int) -> bool:
        command = RemoveImageInput(note_id, version)
        return self._mutate(note_id, partial(self.service.remove, command))

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

    def load(self, note_id: str) -> bool:
        """Request a thumbnail; any earlier request becomes stale."""
        if not self._alive:
            return False
        request_id = LOAD + ":" + uuid4().hex
        self._load = (request_id, note_id)
        task = partial(self.service.get, GetImageInput(note_id))
        if not self.runner.submit(request_id, LOAD, task):
            self._load = None
            self.on_load_failed(note_id, ErrorCode.BUSY)
            return False
        return True

    def forget_load(self) -> None:
        self._load = None

    def handle(self, event: TaskEvent) -> None:
        if not self._alive:
            return
        if event.operation == MUTATE and self._change and event.request_id == self._change[0]:
            self._change = None
            self.on_busy(False)
            if event.result.ok:
                self.on_changed(event.result.value)
            else:
                self.on_change_failed(event.result.error)
        elif event.operation == LOAD and self._load and event.request_id == self._load[0]:
            note_id, self._load = self._load[1], None
            if event.result.ok:
                self.on_loaded(note_id, event.result.value)
            else:
                self.on_load_failed(note_id, event.result.error)

    def close(self) -> None:
        self._alive = False
        self._change = self._load = None
