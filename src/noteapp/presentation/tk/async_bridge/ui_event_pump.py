"""Only the owner thread schedules and cancels Tk callbacks."""

from collections.abc import Callable
from threading import get_ident

from noteapp.presentation.tk.async_bridge.task_runner import TaskEvent, TaskRunner


class UIEventPump:
    def __init__(
        self, root, runner: TaskRunner, dispatch: Callable[[TaskEvent], None], interval_ms: int = 50
    ) -> None:
        self.root, self.runner, self.dispatch = root, runner, dispatch
        self.interval_ms = interval_ms
        self._owner = get_ident()
        self._after_id = None
        self._closed = False

    def _assert_owner(self) -> None:
        if get_ident() != self._owner:
            raise RuntimeError("Tk event pump must run on its owner thread.")

    def start(self) -> None:
        self._assert_owner()
        if not self._closed and self._after_id is None:
            self._after_id = self.root.after(self.interval_ms, self._poll)

    def _poll(self) -> None:
        self._assert_owner()
        self._after_id = None
        if self._closed:
            return
        for event in self.runner.drain():
            if self._closed:
                return
            self.dispatch(event)
        self.start()

    def close(self) -> None:
        self._assert_owner()
        self._closed = True
        if self._after_id is not None:
            self.root.after_cancel(self._after_id)
            self._after_id = None
