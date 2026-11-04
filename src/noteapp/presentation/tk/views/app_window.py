"""Three-pane shell; only presenters access public use cases."""

from collections.abc import Callable
from functools import partial
from uuid import uuid4

import ttkbootstrap as ttk
from ttkbootstrap.utility import scale_size

from noteapp.application.commands.category import CategoryTools
from noteapp.application.commands.create import CreateNote
from noteapp.application.commands.purge import PurgeNote
from noteapp.application.commands.restore import RestoreNote
from noteapp.application.commands.set_reminder import ReminderTools
from noteapp.application.commands.trash import TrashNote
from noteapp.application.commands.update import UpdateNote
from noteapp.application.dto.note_input import (
    ListTrashInput,
    Priority,
    PurgeNoteInput,
    RestoreNoteInput,
    TrashNoteInput,
)
from noteapp.application.dto.note_view import CategoryView, ImageContent, NoteView
from noteapp.application.dto.operation_result import ErrorCode, OperationResult
from noteapp.application.queries.list_notes import ListNotes
from noteapp.application.queries.list_trash import ListTrash
from noteapp.application.queries.search_notes import SearchNotes
from noteapp.application.services.attachment_service import AttachmentService
from noteapp.application.services.reminder_service import DeliveryReport
from noteapp.presentation.tk.async_bridge.task_runner import TaskEvent, TaskRunner
from noteapp.presentation.tk.async_bridge.ui_event_pump import UIEventPump
from noteapp.presentation.tk.presenters.attachment_presenter import AttachmentPresenter
from noteapp.presentation.tk.presenters.category_presenter import CategoryPresenter
from noteapp.presentation.tk.presenters.editor_presenter import EditorPresenter
from noteapp.presentation.tk.presenters.notes_presenter import NotesPresenter
from noteapp.presentation.tk.presenters.reminder_presenter import ReminderPresenter
from noteapp.presentation.tk.state.editor_state import EditorPhase
from noteapp.presentation.tk.views.category_dialog import CategoryDialog
from noteapp.presentation.tk.views.dialogs import (
    ask_category_color,
    ask_category_name,
    ask_image_file,
    confirm_delete_category,
    confirm_discard,
    confirm_purge,
    confirm_remove_image,
    confirm_trash,
)
from noteapp.presentation.tk.views.icons import create_icons
from noteapp.presentation.tk.views.note_editor import NOTIFICATION_FAILED, NoteEditor
from noteapp.presentation.tk.views.note_list import NoteList
from noteapp.presentation.tk.views.reminder_dialog import ask_reminder_time
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
        categories: CategoryTools | None = None,
        attachments: AttachmentService | None = None,
        reminders: ReminderTools | None = None,
        reminder_scan: Callable[[], DeliveryReport] | None = None,
        reminder_start: Callable[[], object] | None = None,
        reminder_stop: Callable[[], object] | None = None,
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
        self.reminder_scan, self.reminder_start = reminder_scan, reminder_start
        self.reminder_stop = reminder_stop
        self._reminder_scan_id = None
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
            panes,
            self.new_note,
            self.query_changed,
            self.switch_mode,
            self.icons,
            self.open_category_manager if categories is not None else None,
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
            self.choose_image if attachments is not None else None,
            self.remove_image if attachments is not None else None,
            self.set_reminder if reminders is not None else None,
            self.cancel_reminder if reminders is not None else None,
        )
        if reminders is not None:
            self.note_editor.local_timezone = reminders.set.local_timezone
        for column, (widget, weight) in enumerate(
            ((self.sidebar, 2), (self.note_list, 3), (self.note_editor, 5))
        ):
            panes.columnconfigure(column, weight=weight, uniform="noteapp_panes")
            widget.grid(row=0, column=column, sticky="nsew")
        self.notes = NotesPresenter(search or list_notes, runner, self.note_list.render)
        self.editor = EditorPresenter(
            create, update, runner, self.render_editor, self.notes.refresh
        )
        self.category_view: tuple[CategoryView, ...] = ()
        self.category_dialog: CategoryDialog | None = None
        self.category_presenter = (
            CategoryPresenter(
                categories,
                runner,
                self.categories_changed,
                self.category_failed,
                self.category_busy,
            )
            if categories is not None
            else None
        )
        self._image_key: tuple | None = None
        self.attachment_presenter = (
            AttachmentPresenter(
                attachments,
                runner,
                self.image_changed,
                self.image_change_failed,
                self.image_loaded,
                self.image_load_failed,
                self.image_busy,
            )
            if attachments is not None
            else None
        )
        self.reminder_presenter = (
            ReminderPresenter(
                reminders,
                runner,
                self.reminder_changed,
                self.reminder_change_failed,
                self.reminder_busy,
            )
            if reminders is not None
            else None
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
                self.categories_changed(event.result.value)
                self.sidebar.set_categories_ready()
                self.notes.refresh()
                if self.maintenance is not None and self._maintenance_id is None:
                    self._maintenance_id = self.root.after(60000, self.run_maintenance)
                self.start_reminders()
            else:
                self.note_list.message.configure(
                    text="Không kết nối được. Chọn Làm mới để thử lại.", bootstyle="danger"
                )
        self.editor.handle(event)
        self.notes.handle(event)
        self.handle_mutation(event)
        if self.category_presenter is not None:
            self.category_presenter.handle(event)
        if self.attachment_presenter is not None:
            self.attachment_presenter.handle(event)
        if self.reminder_presenter is not None:
            self.reminder_presenter.handle(event)
        self.handle_reminder_event(event)

    def start_reminders(self) -> None:
        """Missed-reminder scan first; the poller starts only after the scan finished."""
        if self.reminder_presenter is not None:
            self.note_editor.local_timezone = self.reminder_presenter.tools.set.local_timezone
        if self.reminder_scan is None or self._reminder_scan_id is not None:
            return
        self._reminder_scan_id = "reminder_scan:" + uuid4().hex
        if not self.runner.submit(self._reminder_scan_id, "reminder_scan", self.reminder_scan):
            self._reminder_scan_id = None
            self._start_poller()

    def _start_poller(self) -> None:
        if self.alive and self.reminder_start is not None:
            self.reminder_start()

    def handle_reminder_event(self, event: TaskEvent) -> None:
        if event.operation == "reminder_scan" and event.request_id == self._reminder_scan_id:
            self._start_poller()
        elif event.operation not in ("reminder_scan", "reminder_poll"):
            return
        report = event.result.value if event.result.ok else None
        if isinstance(report, DeliveryReport) and report.noteworthy:
            self.reminders_delivered(report)

    def reminders_delivered(self, report: DeliveryReport) -> None:
        if not self.alive:
            return
        delivered = {item.note_id: item.delivered_at for item in report.delivered}
        if delivered:
            self.notes.refresh()
        if self.editor.apply_delivered(delivered):
            self.render_editor(self.editor.state)
        if self.editor.state.note_id in report.failed_note_ids:
            self.note_editor.show_reminder_message(NOTIFICATION_FAILED, True)

    def categories_changed(self, categories: tuple[CategoryView, ...]) -> None:
        if not self.alive:
            return
        self.category_view = categories
        self.sidebar.set_categories(categories)
        self.note_editor.set_categories(categories)
        if self.category_dialog is not None:
            self.category_dialog.render(categories)

    def category_failed(self, code: ErrorCode) -> None:
        if self.alive and self.category_dialog is not None:
            self.category_dialog.show_error(code)

    def category_busy(self, busy: bool) -> None:
        if self.alive and self.category_dialog is not None:
            self.category_dialog.set_busy(busy)

    def open_category_manager(self) -> None:
        if not self.alive or self.category_presenter is None:
            return
        if self.category_dialog is not None:
            self.category_dialog.lift()
            return
        self.category_dialog = CategoryDialog(
            self.root,
            self.add_category,
            self.rename_category,
            self.recolor_category,
            self.delete_category,
            self._category_dialog_closed,
        )
        self.category_dialog.render(self.category_view)
        self.category_dialog.set_busy(self.category_presenter.busy)

    def _category_dialog_closed(self) -> None:
        self.category_dialog = None

    def add_category(self) -> None:
        name = ask_category_name(self.category_dialog, "Thêm danh mục")
        if name is not None and self.category_presenter is not None:
            self.category_presenter.add(name)

    def rename_category(self, category: CategoryView) -> None:
        name = ask_category_name(self.category_dialog, "Đổi tên danh mục", category.name)
        if name is not None and self.category_presenter is not None:
            self.category_presenter.rename(category.category_id, name)

    def recolor_category(self, category: CategoryView) -> None:
        color = ask_category_color(self.category_dialog, category.color_hex)
        if color is not None and self.category_presenter is not None:
            self.category_presenter.recolor(category.category_id, color)

    def delete_category(self, category: CategoryView) -> None:
        if (
            confirm_delete_category(self.category_dialog, category.name)
            and self.category_presenter is not None
        ):
            self.category_presenter.delete(category.category_id)

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
        self.note_editor.set_attachment_busy(self._image_in_flight())
        self.note_editor.set_reminder_busy(self._reminder_in_flight())
        self.note_editor.render(state, reload_fields)
        self.note_editor.set_busy(self._mutation_pending is not None or self._change_in_flight())
        self._sync_image(state)

    def _image_in_flight(self) -> bool:
        return self.attachment_presenter is not None and self.attachment_presenter.busy

    def _reminder_in_flight(self) -> bool:
        return self.reminder_presenter is not None and self.reminder_presenter.busy

    def _change_in_flight(self) -> bool:
        return self._image_in_flight() or self._reminder_in_flight()

    def _sync_image(self, state) -> None:
        """Load the preview when the note or its image changed; stale loads are dropped."""
        if self.attachment_presenter is None:
            return
        key = (state.note_id, state.attachment, self.mode)
        if key == self._image_key:
            return
        self._image_key = key
        self.attachment_presenter.forget_load()
        if state.attachment is not None and self.mode == "active":
            self.note_editor.show_attachment_message("Đang tải ảnh…")
            self.attachment_presenter.load(state.note_id)

    def _can_change_image(self) -> bool:
        state = self.editor.state
        return (
            self.alive
            and self.attachment_presenter is not None
            and self.mode == "active"
            and state.note_id is not None
            and not self._change_in_flight()
            and not self.editor.saving
            and self._mutation_pending is None
            and state.phase not in (EditorPhase.SAVING, EditorPhase.CONFLICT)
        )

    def choose_image(self) -> None:
        if not self._can_change_image():
            return
        note_id = self.editor.state.note_id
        path = ask_image_file(self.root)
        # The file dialog runs a nested loop: re-check before touching anything.
        if path is None or not self._can_change_image() or self.editor.state.note_id != note_id:
            return
        self.note_editor.show_attachment_message("Đang tải ảnh lên…")
        self.attachment_presenter.attach(note_id, self.editor.state.version, path)

    def remove_image(self) -> None:
        if (
            self._can_change_image()
            and self.editor.state.attachment is not None
            and confirm_remove_image(self.root)
            and self._can_change_image()
        ):
            self.note_editor.show_attachment_message("Đang gỡ ảnh…")
            self.attachment_presenter.remove(self.editor.state.note_id, self.editor.state.version)

    def _can_change_reminder(self) -> bool:
        state = self.editor.state
        return (
            self.alive
            and self.reminder_presenter is not None
            and self.mode == "active"
            and state.note_id is not None
            and not self._change_in_flight()
            and not self.editor.saving
            and self._mutation_pending is None
            and state.phase not in (EditorPhase.SAVING, EditorPhase.CONFLICT)
        )

    def set_reminder(self) -> None:
        if not self._can_change_reminder():
            return
        note_id = self.editor.state.note_id
        initial = self._reminder_initial()
        due_at = ask_reminder_time(self.root, initial)
        # The dialog runs a nested loop: re-check before touching anything.
        if due_at is None or not self._can_change_reminder():
            return
        if self.editor.state.note_id != note_id:
            return
        self.reminder_presenter.set(note_id, self.editor.state.version, due_at)

    def _reminder_initial(self):
        reminder = self.editor.state.reminder
        if reminder is None or reminder.status != "ACTIVE":
            return None
        zone = self.note_editor.local_timezone
        return reminder.due_at.astimezone(zone).replace(tzinfo=None)

    def cancel_reminder(self) -> None:
        state = self.editor.state
        if self._can_change_reminder() and state.reminder and state.reminder.status == "ACTIVE":
            self.reminder_presenter.cancel(state.note_id, state.version)

    def reminder_busy(self, _busy: bool) -> None:
        if self.alive:
            self.render_editor(self.editor.state)

    def reminder_changed(self, saved: NoteView) -> None:
        if not self.alive:
            return
        self.editor.apply_reminder(saved)
        self.notes.refresh()
        self.render_editor(self.editor.state)

    def reminder_change_failed(self, code: ErrorCode) -> None:
        if not self.alive:
            return
        if code == ErrorCode.CONFLICT:
            self.editor.state.phase = EditorPhase.CONFLICT
            self.editor.state.error = code
        self.render_editor(self.editor.state)
        self.note_editor.show_reminder_error(code)

    def image_busy(self, _busy: bool) -> None:
        if self.alive:
            self.render_editor(self.editor.state)

    def image_changed(self, saved: NoteView) -> None:
        if not self.alive:
            return
        self.editor.apply_attachment(saved)
        self.notes.refresh()
        self.render_editor(self.editor.state)

    def image_change_failed(self, code: ErrorCode) -> None:
        if not self.alive:
            return
        if code == ErrorCode.CONFLICT:
            self.editor.state.phase = EditorPhase.CONFLICT
            self.editor.state.error = code
        self.render_editor(self.editor.state)
        self.note_editor.show_attachment_error(code)

    def image_loaded(self, note_id: str, content: ImageContent) -> None:
        state = self.editor.state
        if self.alive and note_id == state.note_id and state.attachment is not None:
            self.note_editor.show_preview(content)
            self.note_editor.clear_attachment_message()
            self.render_editor(state)

    def image_load_failed(self, note_id: str, _code: ErrorCode) -> None:
        if self.alive and note_id == self.editor.state.note_id:
            self.note_editor.show_attachment_message(
                "Không tải được bản xem trước ảnh. Kiểm tra kết nối rồi mở lại ghi chú.", True
            )

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
        if (
            self._mutation_pending is not None
            or state.phase == EditorPhase.SAVING
            or self._change_in_flight()
        ):
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
        if (
            self.mode == "active"
            and self._mutation_pending is None
            and not self._change_in_flight()
        ):
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
        if self.category_presenter is not None:
            self.category_presenter.close()
        if self.attachment_presenter is not None:
            self.attachment_presenter.close()
        if self.reminder_presenter is not None:
            self.reminder_presenter.close()
        if self.reminder_stop is not None:
            self.reminder_stop()
        if self.category_dialog is not None:
            self.category_dialog.destroy()
            self.category_dialog = None
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
