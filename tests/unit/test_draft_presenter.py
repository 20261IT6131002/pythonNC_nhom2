"""Deterministic debounce, stale callbacks and revision-aware remote ACK cleanup."""

from dataclasses import replace

from noteapp.application.commands.create import CreateNote
from noteapp.application.commands.update import UpdateNote
from noteapp.application.dto.operation_result import ErrorCode, OperationResult
from noteapp.application.services.draft_recovery import DraftRecoveryService
from noteapp.presentation.tk.presenters.draft_presenter import DraftPresenter
from noteapp.presentation.tk.presenters.editor_presenter import EditorPresenter
from noteapp.presentation.tk.state.editor_state import EditorPhase
from noteapp.presentation.tk.state.sync_state import SyncState
from tests.draft_fakes import FakeDraftStore
from tests.fakes import FakeCategories, FakeClock, FakeNotes
from tests.unit.test_presenters import ManualRunner


class ManualScheduler:
    def __init__(self):
        self.tasks = {}
        self.sequence = 0

    def after(self, delay, callback):
        self.sequence += 1
        self.tasks[self.sequence] = (delay, callback)
        return self.sequence

    def after_cancel(self, token):
        self.tasks.pop(token, None)

    def fire(self):
        tasks, self.tasks = self.tasks, {}
        for _, callback in tasks.values():
            callback()


def presenters():
    notes, categories, clock = FakeNotes(), FakeCategories(), FakeClock()
    store, runner, scheduler = FakeDraftStore(), ManualRunner(), ManualScheduler()
    service = DraftRecoveryService(store, notes, clock)
    status, errors, recovered = [], [], []
    drafts = DraftPresenter(
        service,
        runner,
        scheduler,
        lambda: status.append(True),
        lambda _: None,
        recovered.append,
        errors.append,
    )
    editor = EditorPresenter(
        CreateNote(notes, categories, clock),
        UpdateNote(notes, categories, clock),
        runner,
        lambda state, _: drafts.observe(state),
        lambda: None,
    )
    editor.on_ack = drafts.acknowledge
    editor.new()
    return editor, drafts, store, notes, runner, scheduler, errors, recovered


def change(editor, text):
    editor.edit("Title", text, editor.state.priority, None)


def test_rapid_edits_debounce_to_one_latest_immutable_snapshot():
    editor, drafts, store, _, runner, scheduler, _, _ = presenters()
    change(editor, "first")
    change(editor, "latest")
    assert len(scheduler.tasks) == 1 and not runner.tasks
    assert editor.state.sync == SyncState.LOCAL_PENDING
    scheduler.fire()
    event = runner.complete()
    drafts.handle(event)
    assert store.get(editor.state.draft_id).content == "latest"
    assert editor.state.phase == EditorPhase.DIRTY
    assert editor.state.sync == SyncState.LOCAL_SAVED


def test_ack_before_autosave_completion_does_not_resurrect_a_draft():
    editor, drafts, store, notes, runner, scheduler, _, _ = presenters()
    change(editor, "content")
    scheduler.fire()  # pending draft write, not executed yet
    editor.save()
    editor.handle(runner.complete(1))  # remote write wins the race
    drafts.handle(runner.complete(2))  # ACK cleanup fences revision 1
    drafts.handle(runner.complete(0))  # late draft write is rejected
    assert len(notes.items) == 1 and not store.items
    assert editor.state.phase == EditorPhase.SAVED
    assert editor.state.sync == SyncState.REMOTE


def test_old_ack_keeps_newer_edits_and_rebases_the_next_draft_snapshot():
    editor, drafts, store, _, runner, scheduler, _, _ = presenters()
    change(editor, "first")
    scheduler.fire()
    drafts.handle(runner.complete(0))
    identity = editor.state.draft_id
    editor.save()
    change(editor, "newer text")
    editor.handle(runner.complete(1))
    assert editor.state.phase == EditorPhase.DIRTY
    assert store.get(identity).content == "first"  # never delete before newer local ACK
    scheduler.fire()
    drafts.handle(runner.complete())
    snapshot = store.get(identity)
    assert snapshot.content == "newer text"
    assert snapshot.note_id == editor.state.note_id and snapshot.base_version == 1


def test_old_local_result_cannot_mark_the_latest_revision_saved_or_mutate_a_new_editor():
    editor, drafts, _, _, runner, scheduler, _, _ = presenters()
    change(editor, "first")
    scheduler.fire()
    change(editor, "newer")
    drafts.handle(runner.complete(0))
    assert editor.state.sync == SyncState.LOCAL_PENDING
    editor.new()
    drafts.handle(runner.complete(0))
    assert editor.state.note_id is None and editor.state.content == ""
    assert editor.state.sync == SyncState.REMOTE


def test_remote_failure_preserves_the_acknowledged_local_copy():
    editor, drafts, store, _, runner, scheduler, _, _ = presenters()
    change(editor, "content")
    scheduler.fire()
    drafts.handle(runner.complete())
    editor.save()
    event = runner.complete()
    editor.handle(replace(event, result=OperationResult(error=ErrorCode.UNAVAILABLE)))
    assert editor.state.phase == EditorPhase.ERROR
    assert editor.state.sync == SyncState.LOCAL_SAVED
    assert store.get(editor.state.draft_id).content == "content"


def test_late_recovery_after_typing_and_closed_presenter_results_are_discarded():
    editor, drafts, _, _, runner, scheduler, errors, recovered = presenters()
    change(editor, "original")
    scheduler.fire()
    drafts.handle(runner.complete())
    drafts.recover(editor.state.draft_id)
    change(editor, "typing while recovery loads")
    drafts.handle(runner.complete())
    assert errors == [ErrorCode.BUSY] and not recovered
    drafts.close()
    assert not scheduler.tasks
    drafts.handle(runner.complete())
    assert not recovered


def test_explicit_discard_of_current_draft_rotates_identity_for_later_edits():
    editor, drafts, store, _, runner, scheduler, _, _ = presenters()
    change(editor, "first")
    scheduler.fire()
    drafts.handle(runner.complete())
    old_identity = editor.state.draft_id
    drafts.discard(old_identity)
    drafts.handle(runner.complete())
    assert store.get(old_identity) is None
    assert editor.state.draft_id != old_identity
    change(editor, "new content after discard")
    scheduler.fire()
    drafts.handle(runner.complete())
    assert store.get(editor.state.draft_id).content == "new content after discard"
