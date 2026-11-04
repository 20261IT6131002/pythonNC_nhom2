"""Async acknowledgements, stale results, paging reset and dirty editor preservation."""

from dataclasses import replace

from noteapp.application.commands.create import CreateNote
from noteapp.application.commands.set_pinned import SetPinned
from noteapp.application.commands.update import UpdateNote
from noteapp.application.dto.note_view import NoteView
from noteapp.application.dto.operation_result import ErrorCode, OperationResult
from noteapp.presentation.tk.async_bridge.task_runner import TaskEvent
from noteapp.presentation.tk.presenters.editor_presenter import EditorPresenter
from noteapp.presentation.tk.presenters.pin_presenter import PIN_OPERATION, PinPresenter
from noteapp.presentation.tk.state.editor_state import EditorPhase
from tests.fakes import FakeCategories, FakeClock, FakeNotes
from tests.repository_contracts import note
from tests.unit.test_presenters import ManualRunner


def test_dirty_editor_keeps_fields_and_saves_using_the_new_pin_version():
    notes, categories, clock, runner = FakeNotes(), FakeCategories(), FakeClock(), ManualRunner()
    original = notes.create(note(), "create")
    editor = EditorPresenter(
        CreateNote(notes, categories, clock),
        UpdateNote(notes, categories, clock),
        runner,
        lambda *_: None,
        lambda: None,
    )
    editor.open(NoteView.from_note(original))
    editor.edit("Unsaved title", "Unsaved content", original.priority, None)
    revision = editor.state.revision

    busy, failures = [], []
    pin = PinPresenter(
        SetPinned(notes),
        runner,
        editor.apply_pinned,
        lambda *args: failures.append(args),
        busy.append,
    )
    assert pin.set(original.id, 1, True)
    assert not pin.set(original.id, 1, False)
    assert not editor.state.is_pinned
    pin.handle(runner.complete())

    assert editor.state.is_pinned and editor.state.version == 2
    assert editor.state.title == "Unsaved title"
    assert editor.state.content == "Unsaved content"
    assert editor.state.revision == revision and editor.state.phase == EditorPhase.DIRTY
    assert busy == [True, False] and not failures

    editor.save()
    editor.handle(runner.complete())
    assert editor.state.phase == EditorPhase.SAVED and editor.state.version == 3
    assert notes.find_by_id(original.id).content == "Unsaved content"
    assert notes.find_by_id(original.id).is_pinned


def test_pin_errors_busy_stale_and_closed_results():
    runner, changed, failed, busy = ManualRunner(), [], [], []
    presenter = PinPresenter(
        SetPinned(FakeNotes()),
        runner,
        changed.append,
        lambda *args: failed.append(args),
        busy.append,
    )
    presenter.set("missing", 1, True)
    event = runner.complete()
    presenter.handle(replace(event, request_id="old-request"))
    assert presenter.busy and not failed
    presenter.handle(event)
    assert failed == [("missing", ErrorCode.NOT_FOUND)] and not changed

    runner.accept = False
    assert not presenter.set("missing", 1, True)
    assert failed[-1] == ("missing", ErrorCode.BUSY)

    runner.accept = True
    presenter.set("missing", 1, True)
    event = TaskEvent(runner.tasks[-1][0], PIN_OPERATION, OperationResult(error=ErrorCode.CONFLICT))
    presenter.close()
    presenter.handle(event)
    assert len(failed) == 2 and not presenter.set("missing", 1, True)
