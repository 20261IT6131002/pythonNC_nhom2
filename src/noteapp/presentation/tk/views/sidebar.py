"""Sketch-inspired navigation/filter controls, using public DTOs only."""

import tkinter as tk
from collections.abc import Callable
from datetime import date
from tkinter import Misc

import ttkbootstrap as ttk
from ttkbootstrap.widgets.scrolled import ScrolledFrame

from noteapp.application.dto.note_filter import (
    DateField,
    SearchNotesCriteria,
    SortDirection,
    SortMode,
)
from noteapp.application.dto.note_input import Priority
from noteapp.application.dto.note_view import CategoryView

SORTS = {
    "Cập nhật mới nhất": (SortMode.UPDATED_AT, SortDirection.DESC),
    "Tạo mới nhất": (SortMode.CREATED_AT, SortDirection.DESC),
    "Tạo cũ nhất": (SortMode.CREATED_AT, SortDirection.ASC),
    "Ưu tiên cao trước": (SortMode.PRIORITY, SortDirection.DESC),
    "Danh mục A–Z": (SortMode.CATEGORY, SortDirection.ASC),
}
PRIORITIES = {
    "Tất cả ưu tiên": None,
    "Cao": Priority.HIGH,
    "Vừa": Priority.MEDIUM,
    "Thấp": Priority.LOW,
}


class Sidebar(ScrolledFrame):
    def __init__(
        self,
        master: Misc,
        on_new: Callable[[], object],
        on_change: Callable[[], None] | None = None,
        on_mode: Callable[[str], None] | None = None,
        icons: dict | None = None,
    ) -> None:
        super().__init__(
            master, padding=(14, 14, 30, 14), width=220, autohide=False, style="Sidebar.TFrame"
        )
        self.on_change, self.on_mode = on_change, on_mode
        self.icons = icons or {}
        self._loading = True
        self.categories = {"Tất cả danh mục": None}
        ttk.Label(self, text="NoteApp", font=("Segoe UI", 20, "bold"), style="Sidebar.TLabel").pack(
            anchor="w"
        )
        ttk.Button(
            self,
            text="Ghi chú mới",
            image=self.icons.get("add"),
            compound="left",
            command=on_new,
            bootstyle="primary",
        ).pack(fill="x", pady=(12, 12))
        ttk.Label(self, text="TÌM KIẾM", style="Sidebar.TLabel", font=("Segoe UI", 9, "bold")).pack(
            anchor="w"
        )
        self.text = tk.StringVar()
        self.search_entry = ttk.Entry(self, textvariable=self.text)
        self.search_entry.pack(fill="x", pady=(6, 12))
        self.active_button = ttk.Button(
            self,
            text="Tất cả ghi chú",
            image=self.icons.get("note"),
            compound="left",
            command=lambda: self._mode("active"),
            bootstyle="primary-outline",
        )
        self.active_button.pack(fill="x", pady=(0, 4))
        self.trash_button = ttk.Button(
            self,
            text="Thùng rác",
            image=self.icons.get("delete"),
            compound="left",
            command=lambda: self._mode("trash"),
            bootstyle="secondary-outline",
        )
        self.trash_button.pack(fill="x", pady=(0, 14))
        self.category = tk.StringVar(value="Tất cả danh mục")
        self.priority = tk.StringVar(value="Tất cả ưu tiên")
        self.date_field = tk.StringVar(value="Ngày cập nhật")
        self.start = tk.StringVar()
        self.end = tk.StringVar()
        self.sort = tk.StringVar(value="Cập nhật mới nhất")
        self.filter_controls = [self.search_entry]
        self.category_combo = self._combo("DANH MỤC", self.category, tuple(self.categories))
        self._combo("ƯU TIÊN", self.priority, tuple(PRIORITIES))
        self._combo("LỌC NGÀY", self.date_field, ("Ngày cập nhật", "Ngày tạo"))
        for label, variable in (("Từ (YYYY-MM-DD)", self.start), ("Đến (YYYY-MM-DD)", self.end)):
            ttk.Label(self, text=label, style="Sidebar.TLabel").pack(anchor="w", pady=(4, 3))
            entry = ttk.Entry(self, textvariable=variable)
            entry.pack(fill="x")
            self.filter_controls.append(entry)
        self._combo("SẮP XẾP", self.sort, tuple(SORTS))
        self.reset_button = ttk.Button(
            self,
            text="Xóa bộ lọc",
            image=self.icons.get("filter"),
            compound="left",
            command=self.clear_filters,
            bootstyle="secondary-outline",
        )
        self.reset_button.pack(fill="x", pady=12)
        self.shortcuts = ttk.Label(
            self,
            text="Ctrl+F: Tìm kiếm\nCtrl+N: Tạo mới   Ctrl+S: Lưu",
            style="Sidebar.TLabel",
            wraplength=210,
        )
        self.shortcuts.pack(anchor="w", pady=(8, 0))
        self.bind("<Configure>", self._resize_shortcuts)
        for variable in (
            self.text,
            self.category,
            self.priority,
            self.date_field,
            self.start,
            self.end,
            self.sort,
        ):
            variable.trace_add("write", self._changed)
        self._loading = False

    def _resize_shortcuts(self, event) -> None:
        self.shortcuts.configure(wraplength=max(100, event.width - 60))

    def close(self) -> None:
        self.unbind("<Configure>")
        self.container.unbind("<Configure>")
        self.container.unbind("<Map>")

    def _combo(self, label, variable, values):
        ttk.Label(self, text=label, style="Sidebar.TLabel", font=("Segoe UI", 9, "bold")).pack(
            anchor="w", pady=(12, 5)
        )
        combo = ttk.Combobox(self, textvariable=variable, values=values, state="readonly", width=1)
        combo.pack(fill="x")
        self.filter_controls.append(combo)
        return combo

    def _changed(self, *_args) -> None:
        if not self._loading and self.on_change is not None:
            self.on_change()

    def _mode(self, mode: str) -> None:
        if self.on_mode is not None:
            self.on_mode(mode)

    def set_mode(self, mode: str) -> None:
        self.active_button.configure(bootstyle="primary" if mode == "active" else "primary-outline")
        self.trash_button.configure(bootstyle="primary" if mode == "trash" else "secondary-outline")
        for widget in self.filter_controls:
            widget.configure(
                state=("readonly" if isinstance(widget, ttk.Combobox) else "normal")
                if mode == "active"
                else "disabled"
            )
        self.reset_button.configure(state="normal" if mode == "active" else "disabled")

    def set_categories(self, categories: tuple[CategoryView, ...]) -> None:
        self._loading = True
        self.categories = {
            "Tất cả danh mục": None,
            **{item.name: item.category_id for item in categories},
        }
        self.category_combo.configure(values=tuple(self.categories))
        if self.category.get() not in self.categories:
            self.category.set("Tất cả danh mục")
        self._loading = False

    def criteria(self) -> SearchNotesCriteria:
        sort, direction = SORTS[self.sort.get()]
        return SearchNotesCriteria(
            text=self.text.get(),
            category_id=self.categories[self.category.get()],
            priority=PRIORITIES[self.priority.get()],
            start_date=date.fromisoformat(self.start.get()) if self.start.get() else None,
            end_date=date.fromisoformat(self.end.get()) if self.end.get() else None,
            date_field=DateField.UPDATED_AT
            if self.date_field.get() == "Ngày cập nhật"
            else DateField.CREATED_AT,
            sort=sort,
            direction=direction,
        )

    def clear_filters(self) -> None:
        self._loading = True
        for variable, value in (
            (self.text, ""),
            (self.category, "Tất cả danh mục"),
            (self.priority, "Tất cả ưu tiên"),
            (self.start, ""),
            (self.end, ""),
            (self.date_field, "Ngày cập nhật"),
            (self.sort, "Cập nhật mới nhất"),
        ):
            variable.set(value)
        self._loading = False
        self._changed()
