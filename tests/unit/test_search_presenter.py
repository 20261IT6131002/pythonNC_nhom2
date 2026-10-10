"""P2-08: old query/page/view results never leak into current generation."""

from noteapp.application.dto.note_filter import SearchNotesCriteria
from noteapp.application.dto.note_input import ListTrashInput
from noteapp.application.dto.note_view import NoteListView, TrashListView
from noteapp.application.dto.operation_result import OperationResult
from noteapp.presentation.tk.async_bridge.task_runner import TaskEvent
from noteapp.presentation.tk.presenters.notes_presenter import NotesPresenter
from tests.unit.test_presenters import ManualRunner


class EmptyQuery:
    def execute(self, _command):
        return NoteListView((), "page-two")


def test_invalidation_drops_response_before_debounce_submits_new_request():
    runner = ManualRunner()
    presenter = NotesPresenter(EmptyQuery(), runner, lambda state: None)
    presenter.refresh()
    event = runner.complete()
    presenter.invalidate()
    presenter.handle(event)
    assert presenter.state.next_cursor is None
    presenter.configure(EmptyQuery(), SearchNotesCriteria(text="new"))
    presenter.refresh()
    presenter.handle(runner.complete())
    assert presenter.state.next_cursor == "page-two"
    presenter.refresh(append=True)
    old_page = runner.complete()
    presenter.configure(EmptyQuery(), SearchNotesCriteria(priority="HIGH"))
    presenter.handle(old_page)
    assert presenter.state.items == () and presenter.state.next_cursor is None


def test_mode_change_and_close_drop_old_results():
    runner = ManualRunner()
    presenter = NotesPresenter(EmptyQuery(), runner, lambda state: None)
    presenter.refresh()
    old = runner.complete()
    presenter.configure(EmptyQuery(), ListTrashInput(), "trash")
    presenter.handle(old)
    assert presenter.state.mode == "trash" and presenter.state.next_cursor is None
    presenter.refresh()
    request = runner.tasks[-1][0]
    presenter.handle(TaskEvent(request, "list", OperationResult(value=TrashListView((), None))))
    assert presenter.state.items == () and presenter.state.trash_items == ()
    presenter.close()
    presenter.handle(TaskEvent(request, "list", OperationResult(value=NoteListView((), "stale"))))
    assert presenter.state.next_cursor is None
