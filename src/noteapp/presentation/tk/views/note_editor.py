"""Accessible labels, text status and guarded form updates."""

import tkinter as tk
from collections.abc import Callable

import ttkbootstrap as ttk

from noteapp.application.dto.note_input import Priority
from noteapp.application.dto.note_view import CategoryView
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


class NoteEditor(ttk.Frame):
    def __init__(
        self,
        master: tk.Misc,
        on_edit: Callable[[str, str, Priority, str | None], None],
        on_save: Callable[[], object],
    ) -> None:
        super().__init__(master, padding=24, width=550)
        self.on_edit, self._loading = on_edit, False
        self.categories = {"Chưa phân loại": None}
        header = ttk.Frame(self)
        header.pack(fill="x")
        ttk.Label(header, text="Soạn ghi chú", font=("Segoe UI", 17, "bold")).pack(side="left")
        self.save_button = ttk.Button(header, text="Lưu", command=on_save, bootstyle="primary")
        self.save_button.pack(side="right")
        self.status = ttk.Label(self, text="Chưa chỉnh sửa", wraplength=480)
        self.status.pack(fill="x", pady=(12, 20))
        self.metadata = ttk.Label(self, text="", bootstyle="secondary", wraplength=480)
        self.metadata.pack(anchor="w", pady=(0, 12))
        ttk.Label(self, text="Tiêu đề").pack(anchor="w")
        self.title = tk.StringVar()
        self.title_entry = ttk.Entry(self, textvariable=self.title)
        self.title_entry.pack(fill="x", pady=(6, 16))
        options = ttk.Frame(self)
        options.pack(fill="x", pady=(0, 20))
        ttk.Label(options, text="Ưu tiên").grid(row=0, column=0, sticky="w")
        ttk.Label(options, text="Danh mục").grid(row=0, column=1, sticky="w", padx=(16, 0))
        self.priority = tk.StringVar(value="Vừa")
        self.category = tk.StringVar(value="Chưa phân loại")
        ttk.Combobox(
            options,
            textvariable=self.priority,
            values=tuple(PRIORITIES),
            state="readonly",
            width=10,
        ).grid(row=1, column=0, sticky="ew", pady=(6, 0))
        self.category_combo = ttk.Combobox(
            options, textvariable=self.category, values=tuple(self.categories), state="readonly"
        )
        self.category_combo.grid(row=1, column=1, sticky="ew", padx=(16, 0), pady=(6, 0))
        options.columnconfigure(1, weight=1)
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
        self._loading = True
        self.categories = {
            "Chưa phân loại": None,
            **{item.name: item.category_id for item in categories},
        }
        self.category_combo.configure(values=tuple(self.categories))
        self._loading = False

    def render(self, state: EditorState, reload_fields: bool = False) -> None:
        self.metadata.configure(
            text=("Cập nhật: " + state.updated_at.astimezone().strftime("%d/%m/%Y %H:%M:%S %z"))
            if state.updated_at is not None
            else ""
        )
        if reload_fields:
            self._loading = True
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
