"""Three-pane shell; only presenters access public use cases."""

from functools import partial
from uuid import uuid4

import ttkbootstrap as ttk

from noteapp.application.commands.create import CreateNote
from noteapp.application.commands.update import UpdateNote
from noteapp.application.dto.note_view import NoteView
from noteapp.application.queries.list_notes import ListNotes
from noteapp.presentation.tk.async_bridge.task_runner import TaskEvent, TaskRunner
from noteapp.presentation.tk.async_bridge.ui_event_pump import UIEventPump
from noteapp.presentation.tk.presenters.editor_presenter import EditorPresenter
from noteapp.presentation.tk.presenters.notes_presenter import NotesPresenter
from noteapp.presentation.tk.views.dialogs import confirm_discard
from noteapp.presentation.tk.views.note_editor import NoteEditor
from noteapp.presentation.tk.views.note_list import NoteList
from noteapp.presentation.tk.views.sidebar import Sidebar


class AppWindow:
    def __init__(
        self,
        create: CreateNote,
        update: UpdateNote,
        list_notes: ListNotes,
        runner: TaskRunner,
        initialize,
    ) -> None:
        self.root = ttk.Window(
            title="NoteApp — Ghi chú cá nhân",
            themename="litera",
            size=(1200, 760),
            minsize=(960, 560),
        )
        self.runner, self.initialize = runner, initialize
        self.alive = True
        self._initial_request = None
        panes = ttk.Panedwindow(self.root, orient="horizontal")
        panes.pack(fill="both", expand=True)
        self.sidebar = Sidebar(panes, self.new_note)
        self.note_list = NoteList(panes, self.open_note, self.connect, self.load_more)
        self.note_editor = NoteEditor(panes, self.edit, self.save)
        for widget, weight in ((self.sidebar, 2), (self.note_list, 3), (self.note_editor, 5)):
            panes.add(widget, weight=weight)
        self.notes = NotesPresenter(list_notes, runner, self.note_list.render)
        self.editor = EditorPresenter(
            create, update, runner, self.note_editor.render, self.notes.refresh
        )
        self.pump = UIEventPump(self.root, runner, self.dispatch)
        self.root.protocol("WM_DELETE_WINDOW", self.request_close)
        self.root.bind("<Control-n>", self.new_note)
        self.root.bind("<Control-s>", self.save)
        self.editor.new()
        self.pump.start()
        self.connect()

    def connect(self) -> None:
        if not self.alive:
            return
        self._initial_request = "initialize:" + uuid4().hex
        if not self.runner.submit(self._initial_request, "initialize", partial(self.initialize)):
            self.note_list.message.configure(text="Đang bận. Thử Làm mới sau ít giây.")

    def dispatch(self, event: TaskEvent) -> None:
        if not self.alive:
            return
        if event.operation == "initialize" and event.request_id == self._initial_request:
            if event.result.ok:
                categories = event.result.value
                self.sidebar.set_categories(categories)
                self.note_editor.set_categories(categories)
                self.notes.refresh()
            else:
                self.note_list.message.configure(
                    text="Không kết nối được. Chọn Làm mới để thử lại.", bootstyle="danger"
                )
        self.editor.handle(event)
        self.notes.handle(event)

    def new_note(self, _event=None) -> str:
        if confirm_discard(self.root, self.editor.state):
            self.editor.new()
            self.note_list.tree.selection_remove(*self.note_list.tree.selection())
            self.note_editor.title_entry.focus_set()
        return "break"

    def open_note(self, note: NoteView) -> None:
        if note.note_id == self.editor.state.note_id:
            # Reopening a refreshed row is the explicit reload path after conflict.
            if note.version == self.editor.state.version:
                return
        if confirm_discard(self.root, self.editor.state):
            self.editor.open(note)

    def edit(self, title, content, priority, category_id) -> None:
        self.editor.edit(title, content, priority, category_id)

    def save(self, _event=None) -> str:
        self.editor.save()
        return "break"

    def load_more(self) -> None:
        self.notes.refresh(append=True)

    def request_close(self) -> None:
        if confirm_discard(self.root, self.editor.state):
            self.close()

    def close(self) -> None:
        if not self.alive:
            return
        self.alive = False
        self.pump.close()
        self.editor.close()
        self.notes.close()
        self.runner.close()
        self.root.destroy()
