"""One recent page at a time; selection emits a typed view snapshot."""

from collections.abc import Callable
from tkinter import Misc

import ttkbootstrap as ttk
from ttkbootstrap.utility import scale_size

from noteapp.application.dto.note_view import NoteView
from noteapp.presentation.tk.state.list_state import ListState


class NoteList(ttk.Frame):
    def __init__(
        self,
        master: Misc,
        on_select: Callable[[NoteView], None],
        on_refresh: Callable[[], None],
        on_more: Callable[[], None],
    ) -> None:
        super().__init__(master, padding=16, width=330)
        self.on_select = on_select
        self.items = {}
        ttk.Label(self, text="Ghi chú gần đây", font=("Segoe UI", 15, "bold")).pack(anchor="w")
        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x", pady=12)
        ttk.Button(toolbar, text="Làm mới", command=on_refresh, bootstyle="secondary-outline").pack(
            side="left"
        )
        self.message = ttk.Label(self, text="Đang kết nối…", wraplength=290)
        self.message.pack(anchor="w", pady=(0, 12))
        body = ttk.Frame(self)
        body.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(
            body, columns=("priority",), show="tree headings", selectmode="browse", height=18
        )
        self.tree.heading("#0", text="Tiêu đề")
        self.tree.heading("priority", text="Ưu tiên")
        self.tree.column("#0", width=205, minwidth=100)
        self.tree.column(
            "priority", width=scale_size(self, 85), minwidth=scale_size(self, 70), stretch=False
        )
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(body, orient="vertical", command=self.tree.yview)
        scrollbar.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=scrollbar.set)
        for priority, color in (("HIGH", "#B91C1C"), ("MEDIUM", "#9A3412"), ("LOW", "#166534")):
            self.tree.tag_configure(priority, foreground=color)
        self.tree.bind("<<TreeviewSelect>>", self._select)
        self.more = ttk.Button(
            self, text="Tải thêm", command=on_more, bootstyle="secondary-outline"
        )
        self.more.pack(fill="x", pady=(12, 0))

    def _select(self, _event=None) -> None:
        selection = self.tree.selection()
        if selection and selection[0] in self.items:
            self.on_select(self.items[selection[0]])

    def render(self, state: ListState) -> None:
        self.message.configure(
            text="Đang tải…"
            if state.loading
            else "Không tải được. Chọn Làm mới để thử lại."
            if state.error
            else f"{len(state.items)} ghi chú"
            if state.items
            else "Chưa có ghi chú. Hãy tạo ghi chú mới.",
            bootstyle="danger" if state.error else "secondary",
        )
        new_items = {item.note_id: item for item in state.items}
        # Keep editor selection independent of refresh; changing list rows never edits text.
        if new_items != self.items:
            self.items = new_items
            self.tree.delete(*self.tree.get_children())
            labels = {"HIGH": "Cao", "MEDIUM": "Vừa", "LOW": "Thấp"}
            for item in state.items:
                self.tree.insert(
                    "",
                    "end",
                    iid=item.note_id,
                    text=item.title,
                    values=(labels[item.priority.value],),
                    tags=(item.priority.value,),
                )
        self.more.configure(
            state="normal" if state.next_cursor and not state.loading else "disabled"
        )
