"""Sidebar with a primary compose action and seeded category catalog."""

import ttkbootstrap as ttk

from noteapp.application.dto.note_view import CategoryView


class Sidebar(ttk.Frame):
    def __init__(self, master, on_new) -> None:
        super().__init__(master, padding=20, width=220)
        ttk.Label(self, text="NOTEAPP", font=("Segoe UI", 18, "bold")).pack(anchor="w")
        ttk.Label(self, text="Không gian ghi chú của bạn", bootstyle="secondary").pack(
            anchor="w", pady=(4, 24)
        )
        ttk.Button(self, text="+  Ghi chú mới", command=on_new, bootstyle="primary").pack(fill="x")
        ttk.Label(self, text="Ctrl+N  •  Tạo mới", bootstyle="secondary").pack(anchor="w", pady=8)
        ttk.Separator(self).pack(fill="x", pady=20)
        ttk.Label(self, text="DANH MỤC", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.catalog = ttk.Frame(self)
        self.catalog.pack(fill="x", pady=12)
        ttk.Label(
            self, text="Chọn danh mục trong trình soạn thảo.", wraplength=175, bootstyle="secondary"
        ).pack(anchor="w", pady=8)
        ttk.Label(self, text="Ctrl+S  •  Lưu ghi chú", bootstyle="secondary").pack(
            side="bottom", anchor="w"
        )

    def set_categories(self, categories: tuple[CategoryView, ...]) -> None:
        for child in self.catalog.winfo_children():
            child.destroy()
        for name in ("Chưa phân loại", *(category.name for category in categories)):
            ttk.Label(self.catalog, text=name, wraplength=175).pack(anchor="w", pady=6)
