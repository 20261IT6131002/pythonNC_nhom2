"""Three-pane shell; only presenters access public use cases."""

from collections.abc import Callable
from functools import partial
from uuid import uuid4

import ttkbootstrap as ttk
from ttkbootstrap.utility import scale_size

from noteapp.application.commands.create import CreateNote
from noteapp.application.commands.purge import PurgeNote
from noteapp.application.commands.restore import RestoreNote
from noteapp.application.commands.trash import TrashNote
from noteapp.application.commands.update import UpdateNote
from noteapp.application.dto.note_input import (
    ListTrashInput,
    Priority,
    PurgeNoteInput,
    RestoreNoteInput,
    TrashNoteInput,
)
from noteapp.application.dto.note_view import CategoryView, NoteView
from noteapp.application.dto.operation_result import ErrorCode, OperationResult
from noteapp.application.queries.list_notes import ListNotes
from noteapp.application.queries.list_trash import ListTrash
from noteapp.application.queries.search_notes import SearchNotes
from noteapp.presentation.tk.async_bridge.task_runner import TaskEvent, TaskRunner
from noteapp.presentation.tk.async_bridge.ui_event_pump import UIEventPump
from noteapp.presentation.tk.presenters.editor_presenter import EditorPresenter
from noteapp.presentation.tk.presenters.notes_presenter import NotesPresenter
from noteapp.presentation.tk.state.editor_state import EditorPhase
from noteapp.presentation.tk.views.dialogs import confirm_discard, confirm_purge, confirm_trash
from noteapp.presentation.tk.views.icons import create_icons
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
        initialize: Callable[[], tuple[CategoryView, ...]],
        *,
        search: SearchNotes | None = None,
        trash: TrashNote | None = None,
        restore: RestoreNote | None = None,
        purge: PurgeNote | None = None,
        list_trash: ListTrash | None = None,
        icon_data: dict[str, str] | None = None,
        maintenance: Callable[[], object] | None = None,
    ) -> None:
        self.root = ttk.Window(
            title="NoteApp — Ghi chú cá nhân",
            themename="litera",
        )
        width = min(scale_size(self.root, 1200), int(self.root.winfo_screenwidth() * 0.9))
        height = min(scale_size(self.root, 760), int(self.root.winfo_screenheight() * 0.85))
        x = max(0, (self.root.winfo_screenwidth() - width) // 2)
        y = max(0, (self.root.winfo_screenheight() - height) // 2)
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        self.root.minsize(
            min(scale_size(self.root, 960), width), min(scale_size(self.root, 560), height)
        )
        self.runner, self.initialize = runner, initialize
        self.search, self.trash, self.restore, self.purge, self.list_trash = (
            search,
            trash,
            restore,
            purge,
            list_trash,
        )
        self.maintenance = maintenance
        self._debounce_id = self._maintenance_id = None
        self._mutation_pending = None
        self.mode = "active"
        self.icons = create_icons(self.root, icon_data or {})
        self.root.style.configure("TFrame", background="#FFFFFF")
        self.root.style.configure("TLabel", background="#FFFFFF", foreground="#172033")
        self.root.style.configure("Sidebar.TFrame", background="#F7F9FD")
        self.root.style.configure("Sidebar.TLabel", background="#F7F9FD", foreground="#475569")
        self.alive = True
        self._initial_request = None
        panes = ttk.Frame(self.root)
        panes.pack(fill="both", expand=True)
        panes.rowconfigure(0, weight=1)
        self.sidebar = Sidebar(
            panes, self.new_note, self.query_changed, self.switch_mode, self.icons
        )
        self.note_list = NoteList(
            panes, self.open_note, self.connect, self.load_more, self.new_note, self.icons
        )
        self.note_editor = NoteEditor(
            panes,
            self.edit,
            self.save,
            self.trash_selected,
            self.restore_selected,
            self.purge_selected,
            self.icons,
        )
        for column, (widget, weight) in enumerate(
            ((self.sidebar, 2), (self.note_list, 3), (self.note_editor, 5))
        ):
            panes.columnconfigure(column, weight=weight, uniform="noteapp_panes")
            widget.grid(row=0, column=column, sticky="nsew")
        self.notes = NotesPresenter(search or list_notes, runner, self.note_list.render)
        self.editor = EditorPresenter(
            create, update, runner, self.render_editor, self.notes.refresh
        )
        self.pump = UIEventPump(self.root, runner, self.dispatch)
        self.root.protocol("WM_DELETE_WINDOW", self.request_close)
        self.root.bind("<Control-n>", self.new_note)
        self.root.bind("<Control-s>", self.save)
        self.root.bind("<Control-f>", self.focus_search)
        self.root.bind("<Delete>", self.delete_key)
        self.editor.new()
        self.root.style.configure("secondary.TLabel", foreground="#475569")
        self.root.style.configure("primary.TButton", background="#2563EB")
        self.root.update_idletasks()
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
                if self.maintenance is not None and self._maintenance_id is None:
                    self._maintenance_id = self.root.after(60000, self.run_maintenance)
            else:
                self.note_list.message.configure(
                    text="Không kết nối được. Chọn Làm mới để thử lại.", bootstyle="danger"
                )
        self.editor.handle(event)
        self.notes.handle(event)
        self.handle_mutation(event)

    def query_changed(self) -> None:
        if not self.alive or self.mode != "active" or self.search is None:
            return
        if self._debounce_id is not None:
            self.root.after_cancel(self._debounce_id)
        self._debounce_id = None
        self.notes.invalidate()
        try:
            criteria = self.sidebar.criteria()
        except (ValueError, KeyError):
            self.notes.invalid_input()
            return
        self.notes.configure(self.search, criteria)
        self.notes.state.loading = True
        self.note_list.render(self.notes.state)
        self._debounce_id = self.root.after(300, self.submit_search)

    def submit_search(self) -> None:
        self._debounce_id = None
        if self.alive:
            self.notes.refresh()

    def render_editor(self, state, reload_fields: bool = False) -> None:
        self.note_editor.render(state, reload_fields)
        self.note_editor.set_busy(self._mutation_pending is not None)

    def switch_mode(self, mode: str) -> bool:
        if not self.alive or mode == self.mode:
            return True
        if mode == "trash" and self.list_trash is None:
            return False
        if not confirm_discard(self.root, self.editor.state):
            return False
        if self._debounce_id is not None:
            self.root.after_cancel(self._debounce_id)
            self._debounce_id = None
        self.mode = mode
        self.sidebar.set_mode(mode)
        self.note_editor.set_mode(mode)
        self.editor.new()
        if mode == "trash":
            self.notes.configure(self.list_trash, ListTrashInput(), "trash")
            self.notes.refresh()
        elif self.search is not None:
            self.query_changed()
        return True

    def focus_search(self, _event=None) -> str:
        if self.switch_mode("active"):
            self.sidebar.search_entry.focus_set()
        return "break"

    def delete_key(self, event) -> str | None:
        if event.widget is self.note_list.canvas and self.mode == "active":
            self.trash_selected()
            return "break"
        return None

    def run_maintenance(self) -> None:
        self._maintenance_id = None
        if self.alive and self.maintenance is not None:
            self.runner.submit("retention:" + uuid4().hex, "retention", self.maintenance)
            self._maintenance_id = self.root.after(60000, self.run_maintenance)

    def start_mutation(self, operation: str, use_case, command) -> None:
        state = self.editor.state
        if self._mutation_pending is not None or state.phase == EditorPhase.SAVING:
            return
        request_id = operation + ":" + uuid4().hex
        self._mutation_pending = (request_id, operation, state.note_id, state.revision)
        self.note_editor.set_busy(True)
        if not self.runner.submit(request_id, operation, partial(use_case.execute, command)):
            self.handle_mutation(
                TaskEvent(request_id, operation, OperationResult(error=ErrorCode.BUSY))
            )

    def trash_selected(self) -> None:
        state = self.editor.state
        if (
            self.mode != "active"
            or self.trash is None
            or state.note_id is None
            or state.phase == EditorPhase.SAVING
        ):
            return
        if confirm_discard(self.root, state) and confirm_trash(self.root):
            self.start_mutation("trash", self.trash, TrashNoteInput(state.note_id, state.version))

    def restore_selected(self) -> None:
        state = self.editor.state
        if self.mode == "trash" and self.restore is not None and state.note_id:
            self.start_mutation(
                "restore", self.restore, RestoreNoteInput(state.note_id, state.version)
            )

    def purge_selected(self) -> None:
        state = self.editor.state
        if (
            self.mode == "trash"
            and self.purge is not None
            and state.note_id
            and confirm_purge(self.root)
        ):
            self.start_mutation(
                "purge", self.purge, PurgeNoteInput(state.note_id, state.version, True)
            )

    def handle_mutation(self, event: TaskEvent) -> None:
        pending = self._mutation_pending
        if pending is None or event.request_id != pending[0] or event.operation != pending[1]:
            return
        self._mutation_pending = None
        _, operation, note_id, revision = pending
        same_editor = (
            self.editor.state.note_id == note_id and self.editor.state.revision == revision
        )
        if event.result.ok:
            if same_editor:
                self.editor.new()
                if operation == "restore" and self.mode == "trash":
                    self.switch_mode("active")
                    self.editor.open(event.result.value)
            elif self.editor.state.note_id == note_id and operation in ("trash", "purge"):
                self.editor.state.phase = EditorPhase.ERROR
                self.editor.state.error = ErrorCode.NOT_FOUND
                self.note_editor.render(self.editor.state, False)
            self.notes.refresh()
        else:
            if self.editor.state.note_id == note_id:
                self.editor.state.phase = (
                    EditorPhase.CONFLICT
                    if event.result.error == ErrorCode.CONFLICT
                    else EditorPhase.ERROR
                )
                self.editor.state.error = event.result.error
            self.note_editor.render(self.editor.state, False)
            self.note_editor.status.configure(
                text="Thao tác chưa hoàn tất. Nội dung được giữ lại; "
                "làm mới để kiểm tra phiên bản hoặc kết nối.",
                bootstyle="danger",
            )
        self.note_editor.set_busy(False)

    def new_note(self, _event=None) -> str:
        if self.mode == "trash" and not self.switch_mode("active"):
            return "break"
        if confirm_discard(self.root, self.editor.state):
            self.editor.new()
            self.note_list.clear_selection()
            self.note_editor.title_entry.focus_set()
        return "break"

    def open_note(self, note: NoteView) -> bool:
        if note.note_id == self.editor.state.note_id:
            # Reopening a refreshed row is the explicit reload path after conflict.
            if note.version == self.editor.state.version:
                return True
        if confirm_discard(self.root, self.editor.state):
            self.editor.open(note)
            return True
        return False

    def edit(self, title: str, content: str, priority: Priority, category_id: str | None) -> None:
        self.editor.edit(title, content, priority, category_id)

    def save(self, _event=None) -> str:
        if self.mode == "active" and self._mutation_pending is None:
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
        for timer in (self._debounce_id, self._maintenance_id):
            if timer is not None:
                self.root.after_cancel(timer)
        self._debounce_id = self._maintenance_id = None
        self._mutation_pending = None
        self.pump.close()
        self.editor.close()
        self.notes.close()
        self.runner.close()
        self.note_list.close()
        self.sidebar.close()
        self.root.destroy()
        # ttkbootstrap 1.x Window.destroy clears an instance attribute, while
        # Style.__new__ consults the class singleton. Release our destroyed root.
        if ttk.Style.get_instance() is self.root.style:
            ttk.Style.instance = None
