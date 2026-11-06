"""Main-thread debounce and immutable worker snapshots; no crypto or file access here."""

from collections.abc import Callable
from functools import partial
from uuid import uuid4

from noteapp.application.dto.local_draft import DraftAck, LocalDraft, RecoveryDecision
from noteapp.application.dto.operation_result import ErrorCode, OperationResult
from noteapp.application.services.draft_recovery import DraftRecoveryService
from noteapp.presentation.tk.async_bridge.task_runner import TaskEvent, TaskRunner
from noteapp.presentation.tk.state.editor_state import EditorState
from noteapp.presentation.tk.state.sync_state import SyncState

AUTOSAVE_DELAY_MS = 750


class DraftPresenter:
    def __init__(
        self,
        service: DraftRecoveryService,
        runner: TaskRunner,
        scheduler,
        on_status: Callable[[], None],
        on_headers: Callable,
        on_recovered: Callable[[RecoveryDecision], None],
        on_error: Callable[[ErrorCode], None],
    ) -> None:
        self.service, self.runner, self.scheduler = service, runner, scheduler
        self.on_status, self.on_headers = on_status, on_headers
        self.on_recovered, self.on_error = on_recovered, on_error
        self._state: EditorState | None = None
        self._snapshots: dict[str, LocalDraft] = {}
        self._signatures: dict[str, tuple] = {}
        self._remote_clean: set[str] = set()
        self._requests: dict[str, tuple[str, str, int]] = {}
        self._timer = None
        self._discover_request = None
        self._recover_request = None
        self._recovery_context = None
        self._alive = True

    @property
    def busy(self) -> bool:
        return any(operation == "draft_write" for operation, _, _ in self._requests.values())

    @staticmethod
    def _signature(state: EditorState) -> tuple:
        return (
            state.note_id,
            state.version,
            state.operation_id,
            state.title,
            state.content,
            state.priority,
            state.category_id,
            state.source_locked,
        )

    @staticmethod
    def _draft_signature(draft: LocalDraft) -> tuple:
        return (
            draft.note_id,
            draft.base_version,
            draft.client_operation_id,
            draft.title,
            draft.content,
            draft.priority,
            draft.category_id,
            draft.source_locked,
        )

    def _cancel_timer(self) -> None:
        if self._timer is not None:
            self.scheduler.after_cancel(self._timer)
            self._timer = None

    def observe(self, state: EditorState, *, active: bool = True) -> None:
        if not self._alive:
            return

        if self._state is not state:
            self.flush()
            self._state = state

        if not active or not state.unsaved or state.revision < 1:
            self._cancel_timer()
            return

        signature = self._signature(state)

        if signature == self._signatures.get(state.draft_id):
            return

        previous = self._snapshots.get(state.draft_id)
        state.draft_revision = max(state.draft_revision, previous.revision if previous else 0) + 1

        try:
            snapshot = LocalDraft(
                state.draft_id,
                state.note_id,
                state.operation_id,
                state.version,
                state.draft_revision,
                state.title,
                state.content,
                state.priority,
                state.category_id,
                self.service.clock.now(),
                state.source_locked,
            )
        except Exception:
            self._failed(state.draft_id, ErrorCode.VALIDATION)
            return

        self._signatures[state.draft_id] = signature
        self._snapshots[state.draft_id] = snapshot
        self._remote_clean.discard(state.draft_id)
        state.sync = SyncState.LOCAL_PENDING
        state.secure_error = None
        self._cancel_timer()
        self._timer = self.scheduler.after(AUTOSAVE_DELAY_MS, self.flush)

    def _submit(self, operation: str, identity: str, revision: int, task: Callable) -> bool:
        request_id = operation + ":" + uuid4().hex
        self._requests[request_id] = (operation, identity, revision)

        if not self.runner.submit(request_id, operation, task):
            self.handle(TaskEvent(request_id, operation, OperationResult(error=ErrorCode.BUSY)))
            return False

        return True

    def flush(self) -> None:
        self._cancel_timer()

        if not self._alive or self._state is None:
            return

        state = self._state
        snapshot = self._snapshots.get(state.draft_id)

        if snapshot is None or state.draft_id in self._remote_clean:
            return

        if any(
            identity == snapshot.draft_id
            and revision == snapshot.revision
            and operation == "draft_write"
            for operation, identity, revision in self._requests.values()
        ):
            return

        self._submit(
            "draft_write",
            snapshot.draft_id,
            snapshot.revision,
            partial(self.service.autosave.execute, snapshot),
        )

    def acknowledge(self, ack: DraftAck) -> None:
        if not self._alive:
            return

        self._remote_clean.add(ack.draft_id)
        self._cancel_timer()

        if self._state is not None and self._state.draft_id == ack.draft_id:
            self._state.sync = SyncState.REMOTE
            self._state.secure_error = None

        self._submit(
            "draft_ack", ack.draft_id, ack.revision, partial(self.service.acknowledge, ack)
        )

    def discover(self) -> None:
        if not self._alive:
            return

        self._discover_request = "draft_discover:" + uuid4().hex

        if not self.runner.submit(
            self._discover_request, "draft_discover", self.service.list_recoverable
        ):
            self.on_error(ErrorCode.BUSY)

    def recover(self, draft_id: str) -> None:
        if not self._alive:
            return

        self._recover_request = "draft_recover:" + uuid4().hex
        self._recovery_context = (self._state, self._state.revision if self._state else 0)

        if not self.runner.submit(
            self._recover_request, "draft_recover", partial(self.service.recover, draft_id)
        ):
            self.on_error(ErrorCode.BUSY)

    def cancel_recovery(self) -> None:
        self._recover_request = None
        self._recovery_context = None

    def discard(self, draft_id: str) -> None:
        if self._alive:
            self._submit("draft_discard", draft_id, 0, partial(self.service.discard, draft_id))

    def _failed(self, identity: str, error: ErrorCode) -> None:
        if self._state is not None and self._state.draft_id == identity:
            self._state.sync = SyncState.SECURE_AUTOSAVE_DISABLED
            self._state.secure_error = error
            self.on_status()

    def handle(self, event: TaskEvent) -> None:
        if not self._alive:
            return

        if event.operation == "draft_discover" and event.request_id == self._discover_request:
            self._discover_request = None
            if event.result.ok:
                self.on_headers(event.result.value)
            else:
                self.on_error(event.result.error)
            return

        if event.operation == "draft_recover" and event.request_id == self._recover_request:
            context = self._recovery_context
            self.cancel_recovery()

            if context != (self._state, self._state.revision if self._state else 0):
                self.on_error(ErrorCode.BUSY)
                return

            if not event.result.ok:
                self.on_error(event.result.error)
                return

            decision = event.result.value

            if decision.draft is not None:
                snapshot = decision.draft
                self._remote_clean.discard(snapshot.draft_id)
                self._snapshots[snapshot.draft_id] = snapshot
                self._signatures[snapshot.draft_id] = self._draft_signature(snapshot)

            self.on_recovered(decision)
            return

        pending = self._requests.get(event.request_id)

        if pending is None or event.operation != pending[0]:
            return

        self._requests.pop(event.request_id)

        operation, identity, revision = pending
        state = self._state

        if operation == "draft_discard":
            if event.result.ok:
                self._snapshots.pop(identity, None)
                self._signatures.pop(identity, None)
                self._remote_clean.add(identity)

                if state is not None and state.draft_id == identity:
                    state.draft_id = str(uuid4())
                    state.draft_revision = 0
                    state.sync = SyncState.LOCAL_PENDING if state.unsaved else SyncState.REMOTE
                    state.secure_error = None
                    self.on_status()

                self.discover()
            else:
                self.on_error(event.result.error)
            return

        snapshot = self._snapshots.get(identity)

        if operation == "draft_ack" and event.result.ok and event.result.value:
            if snapshot is not None and snapshot.revision <= revision:
                self._snapshots.pop(identity, None)
                self._signatures.pop(identity, None)

        if state is None or state.draft_id != identity:
            if (
                operation == "draft_write"
                and snapshot is not None
                and snapshot.revision <= revision
            ):
                self._snapshots.pop(identity, None)
                self._signatures.pop(identity, None)
            return

        if operation == "draft_write":
            if identity in self._remote_clean or revision != state.draft_revision:
                return

            if event.result.ok and event.result.value:
                state.sync = SyncState.LOCAL_SAVED
                state.secure_error = None
            else:
                self._failed(identity, event.result.error or ErrorCode.CONFLICT)
                return
        elif not event.result.ok:
            state.secure_error = event.result.error

        self.on_status()

    def close(self) -> None:
        self._cancel_timer()
        self._alive = False
        self._requests.clear()
        self.cancel_recovery()
