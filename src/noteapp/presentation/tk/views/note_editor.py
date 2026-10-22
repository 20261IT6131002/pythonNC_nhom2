"""Accessible labels, text status and guarded form updates."""

import tkinter as tk
from collections.abc import Callable

import ttkbootstrap as ttk

from noteapp.application.dto.note_input import Priority
from noteapp.application.dto.note_view import AttachmentView, CategoryView, ImageContent
from noteapp.application.dto.operation_result import ErrorCode
from noteapp.presentation.tk.state.editor_state import EditorPhase, EditorState

PRIORITIES = {"Cao": Priority.HIGH, "Vừa": Priority.MEDIUM, "Thấp": Priority.LOW}
ERROR_MESSAGES = {
    ErrorCode.VALIDATION: (
        "Tiêu đề cần 1–250 ký tự; kiểm tra ưu tiên và danh mục. Nội dung được giữ lại."
    ),
    ErrorCode.CONFLICT: "Có phiên bản mới trên máy chủ. Nội dung của bạn được giữ lại. "
    "Làm mới danh sách và chọn lại để tải bản máy chủ, hoặc tạo ghi chú mới.",
    ErrorCode.UNAVAILABLE: (
        "Chưa lưu được vào MongoDB. Nội dung vẫn ở đây; kiểm tra kết nối và thử Lưu lại."
    ),
    ErrorCode.NOT_FOUND: "Ghi chú không còn tồn tại. Nội dung được giữ lại.",
    ErrorCode.BUSY: "Đang có nhiều tác vụ. Nội dung được giữ lại; thử Lưu sau ít giây.",
    ErrorCode.UNEXPECTED: "Chưa lưu được. Nội dung được giữ lại; thử lại hoặc liên hệ nhóm hỗ trợ.",
}
ATTACHMENT_ERRORS = {
    ErrorCode.UNSUPPORTED_IMAGE: "Chỉ hỗ trợ ảnh PNG, JPEG, GIF hoặc WebP.",
    ErrorCode.IMAGE_TOO_LARGE: "Ảnh vượt giới hạn (tối đa 10 MiB và 25 megapixel).",
    ErrorCode.IMAGE_CORRUPT: "Ảnh bị hỏng hoặc không đọc được.",
    ErrorCode.VALIDATION: "Không đọc được tệp đã chọn.",
    ErrorCode.CONFLICT: (
        "Ghi chú đã thay đổi ở nơi khác nên ảnh chưa được đổi. Làm mới rồi thử lại."
    ),
    ErrorCode.NOT_FOUND: "Ghi chú hoặc ảnh không còn tồn tại.",
    ErrorCode.UNAVAILABLE: (
        "Chưa lưu được ảnh do lỗi kết nối hoặc lưu trữ. Ảnh cũ (nếu có) được giữ nguyên."
    ),
    ErrorCode.BUSY: "Đang có nhiều tác vụ. Thử lại sau ít giây.",
    ErrorCode.UNEXPECTED: "Chưa xử lý được ảnh. Thử lại hoặc liên hệ nhóm hỗ trợ.",
}
PREVIEW_MAX_HEIGHT = 180
KIND_LABELS = {"INLINE": "lưu nội tuyến", "GRIDFS": "lưu GridFS"}


def describe_attachment(attachment: AttachmentView) -> str:
    size = attachment.size_bytes
    amount = f"{size / (1024 * 1024):.2f} MiB" if size >= 1024 * 1024 else f"{size / 1024:.1f} KiB"
    return f"{attachment.display_name} • {amount} • {KIND_LABELS.get(attachment.kind, '')}"


class NoteEditor(ttk.Frame):
    def __init__(
        self,
        master: tk.Misc,
        on_edit: Callable[[str, str, Priority, str | None], None],
        on_save: Callable[[], object],
        on_delete: Callable[[], object] | None = None,
        on_restore: Callable[[], object] | None = None,
        on_purge: Callable[[], object] | None = None,
        icons: dict | None = None,
        on_choose_image: Callable[[], object] | None = None,
        on_remove_image: Callable[[], object] | None = None,
    ) -> None:
        super().__init__(master, padding=24, width=550)
        self.on_edit, self._loading = on_edit, False
        self._photo: tk.PhotoImage | None = None
        self._attachment_key: tuple | None = None
        self._attachment_message: tuple[str, bool] | None = None
        self._attachment_busy = False
        icons = icons or {}
        self._trash_mode = False
        self.categories = {"Chưa phân loại": None}
        header = ttk.Frame(self)
        header.pack(fill="x")
        ttk.Label(header, text="Soạn ghi chú", font=("Segoe UI", 17, "bold")).pack(side="left")
        self.save_button = ttk.Button(
            header,
            text="Lưu",
            image=icons.get("save"),
            compound="left",
            command=on_save,
            bootstyle="primary",
        )
        self.save_button.pack(side="right")
        self.delete_button = ttk.Button(
            header,
            text="Xóa",
            image=icons.get("delete"),
            compound="left",
            command=on_delete,
            bootstyle="danger-outline",
        )
        if on_delete is not None:
            self.delete_button.pack(side="right", padx=(8, 12))
        self.restore_button = ttk.Button(
            header,
            text="Khôi phục",
            image=icons.get("restore"),
            compound="left",
            command=on_restore,
            bootstyle="primary",
        )
        self.purge_button = ttk.Button(
            header,
            text="Xóa vĩnh viễn",
            image=icons.get("delete"),
            compound="left",
            command=on_purge,
            bootstyle="danger-outline",
        )
        self.status = ttk.Label(self, text="Chưa chỉnh sửa", wraplength=480)
        self.status.pack(fill="x", pady=(12, 20))
        self.metadata = ttk.Label(self, text="", bootstyle="secondary", wraplength=480)
        self.metadata.pack(anchor="w", pady=(0, 12))
        ttk.Label(self, text="Tiêu đề").pack(anchor="w")
        self.title = tk.StringVar()
        self.title_entry = ttk.Entry(self, textvariable=self.title, font=("Segoe UI", 16, "bold"))
        self.title_entry.pack(fill="x", pady=(6, 16))
        options = ttk.Frame(self)
        options.pack(fill="x", pady=(0, 20))
        ttk.Label(options, text="Ưu tiên").grid(row=0, column=0, sticky="w")
        ttk.Label(options, text="Danh mục").grid(row=0, column=1, sticky="w", padx=(16, 0))
        self.priority = tk.StringVar(value="Vừa")
        self.category = tk.StringVar(value="Chưa phân loại")
        self.priority_combo = ttk.Combobox(
            options,
            textvariable=self.priority,
            values=tuple(PRIORITIES),
            state="readonly",
            width=10,
        )
        self.priority_combo.grid(row=1, column=0, sticky="ew", pady=(6, 0))
        self.category_combo = ttk.Combobox(
            options, textvariable=self.category, values=tuple(self.categories), state="readonly"
        )
        self.category_combo.grid(row=1, column=1, sticky="ew", padx=(16, 0), pady=(6, 0))
        options.columnconfigure(1, weight=1)
        self.image_frame = ttk.Frame(self)
        if on_choose_image is not None:
            self.image_frame.pack(fill="x", pady=(0, 16))
        ttk.Label(self.image_frame, text="Ảnh đính kèm").grid(row=0, column=0, sticky="w")
        self.choose_image_button = ttk.Button(
            self.image_frame,
            text="Chọn ảnh…",
            command=on_choose_image,
            bootstyle="secondary-outline",
        )
        self.choose_image_button.grid(row=0, column=1, sticky="e", padx=(8, 0))
        self.remove_image_button = ttk.Button(
            self.image_frame,
            text="Gỡ ảnh",
            command=on_remove_image,
            bootstyle="danger-outline",
        )
        self.remove_image_button.grid(row=0, column=2, sticky="e", padx=(8, 0))
        self.image_info = ttk.Label(
            self.image_frame, text="", bootstyle="secondary", wraplength=480
        )
        self.image_info.grid(row=1, column=0, columnspan=3, sticky="w", pady=(6, 0))
        self.preview = ttk.Label(self.image_frame)
        self.image_frame.columnconfigure(0, weight=1)
        ttk.Label(self, text="Nội dung").pack(anchor="w")
        text_frame = ttk.Frame(self)
        text_frame.pack(fill="both", expand=True, pady=(6, 0))
        self.content = tk.Text(
            text_frame,
            width=1,
            height=1,
            wrap="word",
            undo=True,
            font=("Segoe UI", 11),
            padx=12,
            pady=12,
            relief="flat",
            highlightthickness=1,
            highlightbackground="#CBD5E1",
            highlightcolor="#2563EB",
        )
        self.content.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(text_frame, command=self.content.yview)
        scroll.pack(side="right", fill="y")
        self.content.configure(yscrollcommand=scroll.set)
        self.content.bind("<<Modified>>", self._text_modified)
        for variable in (self.title, self.priority, self.category):
            variable.trace_add("write", self._changed)
        self._wrap_width = 480
        self.bind("<Configure>", self._resize)

    def _resize(self, event) -> None:
        width = max(180, event.width - 48)
        if width != self._wrap_width:
            self._wrap_width = width
            self.status.configure(wraplength=width)
            self.metadata.configure(wraplength=width)
            self.image_info.configure(wraplength=width)

    def _text_modified(self, _event=None) -> None:
        if self.content.edit_modified():
            self.content.edit_modified(False)
            self._changed()

    def _changed(self, *_args) -> None:
        if not self._loading:
            self.on_edit(
                self.title.get(),
                self.content.get("1.0", "end-1c"),
                PRIORITIES[self.priority.get()],
                self.categories[self.category.get()],
            )

    def set_categories(self, categories: tuple[CategoryView, ...]) -> None:
        """Rebuild the choices, keeping the selected category by ID across renames."""
        selected_id = self.categories.get(self.category.get())
        self._loading = True
        self.categories = {
            "Chưa phân loại": None,
            **{item.name: item.category_id for item in categories},
        }
        self.category_combo.configure(values=tuple(self.categories))
        name = next(
            (key for key, value in self.categories.items() if value == selected_id),
            "Chưa phân loại",
        )
        self.category.set(name)
        self._loading = False
        if self.categories[name] != selected_id:
            self._changed()

    def render(self, state: EditorState, reload_fields: bool = False) -> None:
        self.metadata.configure(
            text=("Cập nhật: " + state.updated_at.astimezone().strftime("%d/%m/%Y %H:%M:%S %z"))
            if state.updated_at is not None
            else ""
        )
        if reload_fields:
            self._loading = True
            self.content.configure(state="normal")
            self.title.set(state.title)
            self.priority.set(
                next(name for name, value in PRIORITIES.items() if value == state.priority)
            )
            self.category.set(
                next(
                    (name for name, value in self.categories.items() if value == state.category_id),
                    "Chưa phân loại",
                )
            )
            self.content.delete("1.0", "end")
            self.content.insert("1.0", state.content)
            self.content.edit_modified(False)
            self.content.edit_reset()
            self._loading = False
            if self._trash_mode:
                self.content.configure(state="disabled")
        labels = {
            EditorPhase.CLEAN: "Chưa chỉnh sửa",
            EditorPhase.DIRTY: "Chưa lưu • Nội dung hiện chỉ được giữ trong phiên này",
            EditorPhase.SAVING: "Đang lưu…",
            EditorPhase.SAVED: f"Đã lưu • Phiên bản {state.version}",
        }
        self.status.configure(
            text=ERROR_MESSAGES.get(state.error, labels.get(state.phase, "Chưa lưu")),
            bootstyle="danger"
            if state.error
            else "success"
            if state.phase == EditorPhase.SAVED
            else "secondary",
            foreground="#B91C1C"
            if state.error
            else "#166534"
            if state.phase == EditorPhase.SAVED
            else "#475569",
        )
        self.save_button.configure(
            state="disabled" if state.phase == EditorPhase.SAVING else "normal"
        )
        self.delete_button.configure(
            state="normal" if state.note_id and state.phase != EditorPhase.SAVING else "disabled"
        )
        for button in (self.restore_button, self.purge_button):
            button.configure(state="normal" if state.note_id else "disabled")
        if self._trash_mode:
            self.status.configure(
                text="Trong thùng rác. Khôi phục để chỉnh sửa.", bootstyle="secondary"
            )
        self._render_attachment(state)

    def _render_attachment(self, state: EditorState) -> None:
        key = (state.note_id, state.attachment)
        if key != self._attachment_key:
            self._attachment_key = key
            self.clear_preview()
            self._attachment_message = None
        if self._attachment_message is not None:
            text, error = self._attachment_message
            self.image_info.configure(text=text, bootstyle="danger" if error else "secondary")
        else:
            if state.attachment is not None:
                text = describe_attachment(state.attachment)
            elif state.note_id is None:
                text = "Lưu ghi chú trước khi đính kèm ảnh."
            else:
                text = "Chưa có ảnh."
            self.image_info.configure(text=text, bootstyle="secondary")
        can_change = (
            not self._trash_mode
            and not self._attachment_busy
            and state.note_id is not None
            and state.phase not in (EditorPhase.SAVING, EditorPhase.CONFLICT)
        )
        self.choose_image_button.configure(
            text="Thay ảnh…" if state.attachment else "Chọn ảnh…",
            state="normal" if can_change else "disabled",
        )
        self.remove_image_button.configure(
            state="normal" if can_change and state.attachment else "disabled"
        )

    def set_attachment_busy(self, busy: bool) -> None:
        self._attachment_busy = busy
        if busy:
            for button in (self.choose_image_button, self.remove_image_button):
                button.configure(state="disabled")

    def show_attachment_error(self, code: ErrorCode) -> None:
        self.show_attachment_message(
            ATTACHMENT_ERRORS.get(code, ATTACHMENT_ERRORS[ErrorCode.UNEXPECTED]), True
        )

    def show_attachment_message(self, text: str, error: bool = False) -> None:
        self._attachment_message = (text, error)
        self.image_info.configure(text=text, bootstyle="danger" if error else "secondary")

    def clear_attachment_message(self) -> None:
        self._attachment_message = None

    def show_preview(self, content: ImageContent) -> None:
        photo = tk.PhotoImage(master=self, data=content.png)
        factor = max(1, -(-content.height // PREVIEW_MAX_HEIGHT))
        self._photo = photo.subsample(factor) if factor > 1 else photo
        self.preview.configure(image=self._photo)
        self.preview.grid(row=2, column=0, columnspan=3, sticky="w", pady=(8, 0))

    def clear_preview(self) -> None:
        self._photo = None
        self.preview.grid_remove()
        self.preview.configure(image="")

    def set_mode(self, mode: str) -> None:
        self._trash_mode = mode == "trash"
        self.title_entry.configure(state="disabled" if self._trash_mode else "normal")
        for widget in (self.priority_combo, self.category_combo):
            widget.configure(state="disabled" if self._trash_mode else "readonly")
        self.content.configure(state="disabled" if self._trash_mode else "normal")
        for button in (
            self.save_button,
            self.delete_button,
            self.restore_button,
            self.purge_button,
        ):
            button.pack_forget()
        buttons = (
            (self.purge_button, self.restore_button)
            if self._trash_mode
            else (self.save_button, self.delete_button)
        )
        for button in buttons:
            button.pack(side="right", padx=(8, 0))

    def set_busy(self, busy: bool) -> None:
        if busy:
            for button in (
                self.save_button,
                self.delete_button,
                self.restore_button,
                self.purge_button,
            ):
                button.configure(state="disabled")
