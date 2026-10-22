"""Category management window: list plus add/rename/recolor/delete; no persistence here."""

import tkinter as tk
from collections.abc import Callable

import ttkbootstrap as ttk

from noteapp.application.dto.note_view import CategoryView
from noteapp.application.dto.operation_result import ErrorCode

MESSAGES = {
    ErrorCode.DUPLICATE: "Tên danh mục đã tồn tại (không phân biệt hoa/thường).",
    ErrorCode.IN_USE: "Danh mục đang được ghi chú sử dụng nên không thể xóa.",
    ErrorCode.VALIDATION: "Tên không được để trống và màu phải có dạng #RRGGBB.",
    ErrorCode.NOT_FOUND: "Danh mục không còn tồn tại. Danh sách đã được làm mới.",
    ErrorCode.UNAVAILABLE: "Chưa thực hiện được vì không kết nối được MongoDB. Thử lại sau.",
    ErrorCode.BUSY: "Đang có nhiều tác vụ. Thử lại sau ít giây.",
    ErrorCode.UNEXPECTED: "Thao tác chưa hoàn tất. Thử lại hoặc liên hệ nhóm hỗ trợ.",
}


class CategoryDialog(tk.Toplevel):
    def __init__(
        self,
        master: tk.Misc,
        on_add: Callable[[], None],
        on_rename: Callable[[CategoryView], None],
        on_color: Callable[[CategoryView], None],
        on_delete: Callable[[CategoryView], None],
        on_close: Callable[[], None],
    ) -> None:
        super().__init__(master)
        self.title("Quản lý danh mục")
        self.transient(master)
        self.minsize(420, 320)
        self._items: dict[str, CategoryView] = {}
        self._on_close = on_close
        body = ttk.Frame(self, padding=16)
        body.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(
            body, columns=("color",), show="tree headings", selectmode="browse", height=10
        )
        self.tree.heading("#0", text="Tên danh mục")
        self.tree.heading("color", text="Màu")
        self.tree.column("color", width=90, stretch=False)
        self.tree.pack(fill="both", expand=True)
        self.message = ttk.Label(body, text="", wraplength=380, bootstyle="secondary")
        self.message.pack(fill="x", pady=(10, 8))
        row = ttk.Frame(body)
        row.pack(fill="x")
        self.buttons = {
            "add": ttk.Button(row, text="Thêm", command=on_add, bootstyle="primary"),
            "rename": ttk.Button(
                row,
                text="Đổi tên",
                command=lambda: self._selected_call(on_rename),
                bootstyle="secondary-outline",
            ),
            "color": ttk.Button(
                row,
                text="Đổi màu",
                command=lambda: self._selected_call(on_color),
                bootstyle="secondary-outline",
            ),
            "delete": ttk.Button(
                row,
                text="Xóa",
                command=lambda: self._selected_call(on_delete),
                bootstyle="danger-outline",
            ),
        }
        for button in self.buttons.values():
            button.pack(side="left", padx=(0, 8))
        self.protocol("WM_DELETE_WINDOW", self.close)

    def _selected_call(self, callback: Callable[[CategoryView], None]) -> None:
        selected = self.tree.selection()
        if selected and selected[0] in self._items:
            callback(self._items[selected[0]])
        else:
            self.message.configure(text="Chọn một danh mục trong danh sách.")

    def render(self, categories: tuple[CategoryView, ...]) -> None:
        kept = self.tree.selection()
        self.tree.delete(*self.tree.get_children())
        self._items = {item.category_id: item for item in categories}
        for item in categories:
            tag = "c" + item.category_id
            self.tree.tag_configure(tag, foreground=item.color_hex)
            self.tree.insert(
                "",
                "end",
                iid=item.category_id,
                text=item.name,
                values=(item.color_hex,),
                tags=(tag,),
            )
        if kept and kept[0] in self._items:
            self.tree.selection_set(kept[0])
        self.message.configure(
            text="" if categories else "Chưa có danh mục. Chọn Thêm để tạo mới.",
            bootstyle="secondary",
        )

    def show_error(self, code: ErrorCode) -> None:
        self.message.configure(
            text=MESSAGES.get(code, MESSAGES[ErrorCode.UNEXPECTED]), bootstyle="danger"
        )

    def set_busy(self, busy: bool) -> None:
        for button in self.buttons.values():
            button.configure(state="disabled" if busy else "normal")

    def close(self) -> None:
        self._on_close()
        self.destroy()
