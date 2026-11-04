"""Real Tk pin interactions with deterministic worker gates and an in-memory port."""

from threading import Event

from noteapp.application.commands.create import CreateNote
from noteapp.application.commands.set_pinned import SetPinned
from noteapp.application.commands.update import UpdateNote
from noteapp.application.queries.list_notes import ListNotes
from noteapp.domain.errors import RepositoryUnavailable
from noteapp.presentation.tk.async_bridge.task_runner import TaskRunner
from noteapp.presentation.tk.state.editor_state import EditorPhase
from noteapp.presentation.tk.views.app_window import AppWindow
from tests.fakes import FakeCategories, FakeClock, FakeNotes
from tests.repository_contracts import note
from tests.ui_scenarios import drive


def test_pin_flow(monkeypatch):
    entered, release = Event(), Event()

    class GatedNotes(FakeNotes):
        gated = False
        unavailable = False

        def set_pinned_if_version(self, changed, expected):
            if self.gated:
                entered.set()
                assert release.wait(5), "Test did not release the pin worker."
            if self.unavailable:
                raise RepositoryUnavailable("Synthetic outage")
            return super().set_pinned_if_version(changed, expected)

    notes, categories, clock = GatedNotes(), FakeCategories(), FakeClock()
    first = notes.create(note(title="First"), "first")
    second = notes.create(note(title="Second"), "second")
    runner = TaskRunner(max_workers=2)
    app = AppWindow(
        CreateNote(notes, categories, clock),
        UpdateNote(notes, categories, clock),
        ListNotes(notes),
        runner,
        lambda: (),
        pin=SetPinned(notes),
    )
    app.root.withdraw()
    errors = []
    app.root.report_callback_exception = lambda *error: errors.append(error)
    monkeypatch.setattr("noteapp.presentation.tk.views.app_window.confirm_discard", lambda *_: True)

    try:
        drive(app, lambda: len(app.notes.state.items) == 2 and not app.notes.state.loading)
        view = app.note_editor
        assert str(view.pin_button.cget("state")) == "disabled"
        app.open_note(next(item for item in app.notes.state.items if item.note_id == first.id))
        assert view.pin_button.cget("text") == "Ghim"

        view.content.insert("end", " dirty text")
        app.root.update()
        revision = app.editor.state.revision
        notes.gated = True
        view.pin_button.invoke()
        drive(app, entered.is_set)
        assert app.pin_presenter.busy
        assert str(view.pin_button.cget("state")) == "disabled"
        assert str(view.save_button.cget("state")) == "disabled"
        assert not app.note_list._pin_enabled
        assert not app.editor.state.is_pinned

        release.set()
        drive(app, lambda: not app.pin_presenter.busy and not app.notes.state.loading)
        assert app.editor.state.is_pinned and app.editor.state.version == 2
        assert app.editor.state.revision == revision
        assert app.editor.state.phase == EditorPhase.DIRTY
        assert view.content.get("1.0", "end-1c").endswith(" dirty text")
        assert view.pin_button.cget("text") == "Bỏ ghim"
        assert app.notes.state.items[0].note_id == first.id

        app.save()
        drive(app, lambda: app.editor.state.phase == EditorPhase.SAVED)
        assert notes.find_by_id(first.id).content.endswith(" dirty text")
        assert notes.find_by_id(first.id).is_pinned

        # Click the card's actual pin target: it must not open that other note.
        drive(app, lambda: not app.notes.state.loading)
        app.root.deiconify()
        app.root.update()
        target = app.note_list.cards[second.id][6]
        bounds = app.note_list.canvas.bbox(target)
        x, y = (bounds[0] + bounds[2]) // 2, (bounds[1] + bounds[3]) // 2
        app.note_list.canvas.event_generate("<Motion>", x=x, y=y)
        app.note_list.canvas.event_generate("<Button-1>", x=x, y=y)
        app.root.update()
        drive(app, lambda: not app.pin_presenter.busy and not app.notes.state.loading)
        assert notes.find_by_id(second.id).is_pinned
        assert app.editor.state.note_id == first.id
        app.root.withdraw()

        # Failed writes keep the acknowledged flag; a remote version produces conflict.
        notes.unavailable = True
        app.pin_selected()
        drive(app, lambda: not app.pin_presenter.busy)
        assert app.editor.state.is_pinned
        assert "Chưa thể" in app.note_list.message.cget("text")
        notes.unavailable = False
        current = notes.find_by_id(first.id)
        notes.update_if_version(
            current.edited(
                title="Remote",
                content="Remote",
                priority=current.priority,
                category_id=None,
                now=current.updated_at,
            ),
            current.version,
        )
        app.pin_selected()
        drive(app, lambda: app.editor.state.phase == EditorPhase.CONFLICT)
        assert app.editor.state.is_pinned
        assert str(view.pin_button.cget("state")) == "disabled"

        app.note_editor.set_mode("trash")
        assert not view.pin_button.winfo_manager()
        assert not errors, errors
    finally:
        release.set()
        app.close()
        runner.close(wait=True)
