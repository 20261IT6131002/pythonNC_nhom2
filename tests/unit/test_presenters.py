"""P1-AC10: editor/list state transitions, stale results and retry preservation."""

from dataclasses import replace
from uuid import uuid4

import pytest

from noteapp.application.commands.create import CreateNote
from noteapp.application.commands.update import UpdateNote
from noteapp.application.dto.note_input import CreateNoteInput, Priority
from noteapp.application.dto.note_view import NoteListView, NoteView
from noteapp.application.dto.operation_result import ErrorCode, OperationResult
from noteapp.application.queries.list_notes import ListNotes
from noteapp.presentation.tk.async_bridge.task_runner import TaskEvent
from noteapp.presentation.tk.presenters.editor_presenter import EditorPresenter
from noteapp.presentation.tk.presenters.notes_presenter import NotesPresenter
from noteapp.presentation.tk.state.editor_state import EditorPhase
from tests.fakes import FakeCategories, FakeClock, FakeNotes


class ManualRunner:
    def __init__(self):
        self.tasks = []
        self.accept = True

    def submit(self, request_id, operation, task):
        if self.accept:
            self.tasks.append((request_id, operation, task))
        return self.accept

    def complete(self, index=-1):
        request_id, operation, task = self.tasks[index]
        try:
            result = OperationResult(value=task())
        except Exception as error:
            result = OperationResult.failed(error)
        return TaskEvent(request_id, operation, result)


@pytest.fixture
def editor():
    notes, categories, clock, runner = FakeNotes(), FakeCategories(), FakeClock(), ManualRunner()
    changes, saved = [], []
    presenter = EditorPresenter(
        CreateNote(notes, categories, clock),
        UpdateNote(notes, categories, clock),
        runner,
        lambda state, reload: changes.append((state.phase, reload)),
        lambda: saved.append(True),
    )
    return presenter, runner, notes, changes, saved


def edit(presenter, text="Nội dung"):
    presenter.edit("Ghi chú", text, Priority.MEDIUM, None)


def test_editor_saved_only_after_ack(editor):
    presenter, runner, _, changes, saved = editor
    edit(presenter)
    assert presenter.state.phase == EditorPhase.DIRTY
    assert presenter.save()
    assert not presenter.save()
    assert presenter.state.phase == EditorPhase.SAVING
    assert not saved
    presenter.handle(runner.complete())
    assert presenter.state.phase == EditorPhase.SAVED
    assert presenter.state.version == 1
    assert saved == [True]
    assert changes[-1] == (EditorPhase.SAVED, True)


@pytest.mark.parametrize(
    "code",
    [
        ErrorCode.UNAVAILABLE,
        ErrorCode.VALIDATION,
        ErrorCode.CONFLICT,
        ErrorCode.NOT_FOUND,
        ErrorCode.UNEXPECTED,
    ],
)
def test_errors_keep_editor_text(editor, code):
    presenter, runner, _, _, _ = editor
    edit(presenter)
    operation_id = presenter.state.operation_id
    presenter.save()
    request_id = runner.tasks[-1][0]
    presenter.handle(TaskEvent(request_id, "save", OperationResult(error=code)))
    assert presenter.state.content == "Nội dung"
    assert presenter.state.operation_id == operation_id
    expected = EditorPhase.CONFLICT if code == ErrorCode.CONFLICT else EditorPhase.ERROR
    assert presenter.state.phase == expected


def test_invalid_title_keeps_text(editor):
    presenter, runner, notes, _, _ = editor
    presenter.edit(" ", "Keep text", Priority.LOW, None)
    presenter.save()
    presenter.handle(runner.complete())
    assert presenter.state.phase == EditorPhase.ERROR
    assert presenter.state.content == "Keep text"
    assert not notes.items


def test_edits_during_save_are_not_overwritten(editor):
    presenter, runner, notes, _, _ = editor
    edit(presenter, "Before")
    presenter.save()
    edit(presenter, "After")
    presenter.handle(runner.complete())
    assert presenter.state.phase == EditorPhase.DIRTY
    assert presenter.state.content == "After"
    assert notes.find_by_id(presenter.state.note_id).content == "Before"
    presenter.save()
    presenter.handle(runner.complete())
    assert presenter.state.version == 2
    assert presenter.state.phase == EditorPhase.SAVED
    assert notes.find_by_id(presenter.state.note_id).content == "After"


def test_create_timeout_then_changed_retry_does_not_lose_text(editor):
    presenter, runner, notes, _, _ = editor
    edit(presenter, "First payload")
    presenter.save()
    persisted_event = runner.complete()  # DB committed, but delivery was lost.
    presenter.handle(replace(persisted_event, result=OperationResult(error=ErrorCode.UNAVAILABLE)))
    edit(presenter, "Retry payload")
    presenter.save()
    presenter.handle(runner.complete())
    assert len(notes.items) == 1
    assert presenter.state.note_id is not None
    assert presenter.state.content == "Retry payload"
    assert presenter.state.phase == EditorPhase.DIRTY
    presenter.save()
    presenter.handle(runner.complete())
    assert presenter.state.phase == EditorPhase.SAVED
    assert notes.find_by_id(presenter.state.note_id).content == "Retry payload"


def test_switch_editor_discards_old_callback_but_not_committed_db_write(editor):
    presenter, runner, notes, _, saved = editor
    edit(presenter)
    presenter.save()
    presenter.new()
    presenter.handle(runner.complete())
    assert presenter.state.note_id is None
    assert presenter.state.content == ""
    assert len(notes.items) == 1
    assert not saved


def test_closed_presenter_has_no_callbacks(editor):
    presenter, runner, _, changes, saved = editor
    edit(presenter)
    presenter.save()
    presenter.close()
    before = len(changes)
    presenter.handle(runner.complete())
    assert len(changes) == before
    assert not saved


def test_busy_worker_keeps_text(editor):
    presenter, runner, _, _, _ = editor
    runner.accept = False
    edit(presenter)
    assert not presenter.save()
    assert presenter.state.phase == EditorPhase.ERROR
    assert presenter.state.content == "Nội dung"


def test_stale_list_request_ignored():
    notes, runner = FakeNotes(), ManualRunner()
    query = ListNotes(notes)
    presenter = NotesPresenter(query, runner, lambda state: None)
    presenter.refresh()
    presenter.refresh()
    current_event = runner.complete(1)
    presenter.handle(current_event)
    before = presenter.state.items
    old_event = runner.complete(0)
    fake_view = NoteView(
        "old", "old", "", Priority.LOW, None, 1, FakeClock().now(), FakeClock().now()
    )
    presenter.handle(
        replace(old_event, result=OperationResult(value=NoteListView((fake_view,), None)))
    )
    assert presenter.state.items == before


def test_paging_appends_and_close_ignores_results():
    notes, runner = FakeNotes(), ManualRunner()
    create = CreateNote(notes, FakeCategories(), FakeClock())
    for i in range(35):
        create.execute(CreateNoteInput(f"Note {i}", "", Priority.LOW, None, str(uuid4())))
    changes = []
    presenter = NotesPresenter(ListNotes(notes), runner, lambda state: changes.append(True))
    presenter.refresh()
    presenter.handle(runner.complete())
    assert len(presenter.state.items) == 30
    presenter.refresh(append=True)
    presenter.handle(runner.complete())
    assert len(presenter.state.items) == 35
    presenter.refresh()
    presenter.close()
    before = len(changes)
    presenter.handle(runner.complete())
    assert len(changes) == before
