"""Explicit recovery actions; the list exposes opaque identities, never draft plaintext."""

from collections.abc import Callable
from tkinter import messagebox

import ttkbootstrap as ttk

from noteapp.application.dto.local_draft import DraftHeader


class RecoveryDialog(ttk.Toplevel):
    def __init__(
        self, parent, on_recover: Callable, on_discard: Callable, on_closed: Callable
    ) -> None:
        super().__init__(parent)
        self.title("Bản nháp chưa đồng bộ")
        self.transient(parent)
        self.geometry("520x300")
        self.on_recover, self.on_discard, self.on_closed = on_recover, on_discard, on_closed
        self.message = ttk.Label(
            self,
            text="Phát hiện bản nháp chưa đồng bộ. Chọn một bản để khôi phục.",
            wraplength=470,
            padding=16,
        )
        self.message.pack(fill="x")
        self.rows = ttk.Treeview(self, show="tree", selectmode="browse", height=5)
        self.rows.pack(fill="both", expand=True, padx=16)
        actions = ttk.Frame(self, padding=16)
        actions.pack(fill="x")
        self.recover_button = ttk.Button(actions, text="Khôi phục", command=self._recover)
        self.recover_button.pack(side="left")
        ttk.Button(actions, text="Giữ lại", command=self.close, bootstyle="secondary-outline").pack(
            side="right"
        )
        self.discard_button = ttk.Button(
            actions, text="Xóa bản nháp", command=self._discard, bootstyle="danger-outline"
        )
        self.discard_button.pack(side="left", padx=8)
        self.rows.bind("<Return>", lambda _: self._recover())
        self.protocol("WM_DELETE_WINDOW", self.close)

    def render(self, headers: tuple[DraftHeader, ...]) -> None:
        self.rows.delete(*self.rows.get_children())

        for index, header in enumerate(headers, 1):
            self.rows.insert(
                "", "end", iid=header.draft_id, text=f"Bản nháp {index} · {header.draft_id[:8]}"
            )

        if headers:
            self.rows.selection_set(headers[0].draft_id)
            self.rows.focus_set()
        else:
            self.show_message("Không còn bản nháp cần khôi phục.")

    def _recover(self) -> None:
        selected = self.rows.selection()

        if selected:
            self.show_message("Đang kiểm tra bản nháp và phiên bản máy chủ…")
            self.on_recover(selected[0])

    def _discard(self) -> None:
        selected = self.rows.selection()

        if selected and messagebox.askyesno(
            "Xóa bản nháp",
            "Xóa vĩnh viễn bản nháp cục bộ đã chọn?",
            parent=self,
        ):
            self.on_discard(selected[0])

    def show_message(self, message: str) -> None:
        self.message.configure(text=message)

    def close(self) -> None:
        self.on_closed()
        self.destroy()
