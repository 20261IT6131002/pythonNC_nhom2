"""Run category use cases in workers; results return as the refreshed catalog."""

from collections.abc import Callable
from functools import partial
from uuid import uuid4

from noteapp.application.commands.category import CategoryTools
from noteapp.application.dto.note_input import (
    CreateCategoryInput,
    DeleteCategoryInput,
    RenameCategoryInput,
    UpdateCategoryColorInput,
)
from noteapp.application.dto.note_view import CategoryView
from noteapp.application.dto.operation_result import ErrorCode, OperationResult
from noteapp.presentation.tk.async_bridge.task_runner import TaskEvent, TaskRunner

OPERATION = "category"


class CategoryPresenter:
    def __init__(
        self,
        tools: CategoryTools,
        runner: TaskRunner,
        on_categories: Callable[[tuple[CategoryView, ...]], None],
        on_error: Callable[[ErrorCode], None],
        on_busy: Callable[[bool], None],
    ) -> None:
        self.tools, self.runner = tools, runner
        self.on_categories, self.on_error, self.on_busy = on_categories, on_error, on_busy
        self._pending: str | None = None
        self._alive = True

    @property
    def busy(self) -> bool:
        return self._pending is not None

    def add(self, name: str, color_hex: str | None = None) -> bool:
        command = (
            CreateCategoryInput(name) if color_hex is None else CreateCategoryInput(name, color_hex)
        )
        return self._run(self.tools.create, command)

    def rename(self, category_id: str, name: str) -> bool:
        return self._run(self.tools.rename, RenameCategoryInput(category_id, name))

    def recolor(self, category_id: str, color_hex: str) -> bool:
        return self._run(self.tools.recolor, UpdateCategoryColorInput(category_id, color_hex))

    def delete(self, category_id: str) -> bool:
        return self._run(self.tools.delete, DeleteCategoryInput(category_id))

    def refresh(self) -> bool:
        return self._run(None, None)

    def _execute(self, use_case, command) -> tuple[CategoryView, ...]:
        if use_case is not None:
            use_case.execute(command)
        return self.tools.list.execute()

    def _run(self, use_case, command) -> bool:
        if not self._alive or self._pending is not None:
            return False
        request_id = OPERATION + ":" + uuid4().hex
        self._pending = request_id
        self.on_busy(True)
        if not self.runner.submit(request_id, OPERATION, partial(self._execute, use_case, command)):
            self.handle(TaskEvent(request_id, OPERATION, OperationResult(error=ErrorCode.BUSY)))
            return False
        return True

    def handle(self, event: TaskEvent) -> None:
        if not self._alive or event.operation != OPERATION or event.request_id != self._pending:
            return
        self._pending = None
        self.on_busy(False)
        if event.result.ok:
            self.on_categories(event.result.value)
            return
        self.on_error(event.result.error)
        if event.result.error == ErrorCode.NOT_FOUND:
            self.refresh()

    def close(self) -> None:
        self._alive = False
        self._pending = None
