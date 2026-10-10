"""Keyboard accessible, paged note cards inspired by the supplied sketch."""

import tkinter as tk
from collections.abc import Callable
from tkinter import Misc

import ttkbootstrap as ttk

from noteapp.application.dto.note_view import NoteView
from noteapp.presentation.tk.state.list_state import ListState

PRIORITY_STYLE = {
    "HIGH": ("Cao", "#B91C1C", "#FEE2E2"),
    "MEDIUM": ("Vừa", "#92400E", "#FEF3C7"),
    "LOW": ("Thấp", "#166534", "#DCFCE7"),
}


class NoteList(ttk.Frame):
    def __init__(
        self,
        master: Misc,
        on_select: Callable[[NoteView], bool | None],
        on_refresh: Callable[[], None],
        on_more: Callable[[], None],
        on_new: Callable[[], object] | None = None,
        icons: dict | None = None,
    ) -> None:
        super().__init__(master, padding=16, width=330)
        self.on_select, self.icons = on_select, icons or {}
        self.items, self.cards = {}, {}
        self.selected_id = None
        self._mode = "active"
        self.heading = ttk.Label(self, text="Tất cả ghi chú", font=("Segoe UI", 17, "bold"))
        self.heading.pack(anchor="w")
        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x", pady=(10, 12))
        ttk.Button(
            toolbar,
            text="Làm mới",
            image=self.icons.get("refresh"),
            compound="left",
            command=on_refresh,
            bootstyle="secondary-outline",
        ).pack(side="left")
        if on_new is not None:
            ttk.Button(
                toolbar,
                text="Tạo mới",
                image=self.icons.get("add"),
                compound="left",
                command=on_new,
                bootstyle="primary",
            ).pack(side="right")
        self.message = ttk.Label(self, text="Đang kết nối…", wraplength=290)
        self.message.pack(fill="x", pady=(0, 12))
        body = ttk.Frame(self)
        body.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(
            body,
            background="#FFFFFF",
            highlightthickness=1,
            highlightbackground="#E2E8F0",
            highlightcolor="#2563EB",
            takefocus=True,
        )
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(body, orient="vertical", command=self.canvas.yview)
        scrollbar.pack(side="right", fill="y")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.card_container = tk.Frame(self.canvas, background="#FFFFFF")
        self._window = self.canvas.create_window((0, 0), window=self.card_container, anchor="nw")
        self.card_container.bind(
            "<Configure>",
            lambda _event: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )
        self.canvas.bind("<Configure>", self._resize)
        self.canvas.bind("<Down>", lambda _event: self._step(1))
        self.canvas.bind("<Up>", lambda _event: self._step(-1))
        self.canvas.bind("<Return>", lambda _event: self._activate())
        self.canvas.bind("<MouseWheel>", self._wheel)
        self.canvas.bind("<Button-4>", lambda _event: self.canvas.yview_scroll(-1, "units"))
        self.canvas.bind("<Button-5>", lambda _event: self.canvas.yview_scroll(1, "units"))
        self.more = ttk.Button(
            self, text="Tải thêm", command=on_more, bootstyle="secondary-outline"
        )
        self.more.pack(fill="x", pady=(12, 0))

    def _resize(self, event) -> None:
        self.canvas.itemconfigure(self._window, width=event.width)
        self.message.configure(wraplength=max(100, event.width))
        for frame in self.cards.values():
            for child in frame.winfo_children():
                if isinstance(child, tk.Label) and getattr(child, "_wrap", False):
                    child.configure(wraplength=max(100, event.width - 40))

    def close(self) -> None:
        # Geometry events may fire while sibling widgets are being destroyed.
        self.canvas.unbind("<Configure>")
        self.card_container.unbind("<Configure>")

    def _wheel(self, event) -> str:
        self.canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")
        return "break"

    def _step(self, offset: int) -> str:
        keys = list(self.items)
        if keys:
            index = keys.index(self.selected_id) if self.selected_id in keys else -1
            self._choose(keys[max(0, min(len(keys) - 1, index + offset))])
        return "break"

    def _activate(self) -> str:
        if self.selected_id in self.items:
            self.on_select(self.items[self.selected_id])
        return "break"

    def _choose(self, note_id: str) -> None:
        if self.on_select(self.items[note_id]) is False:
            return
        self.selected_id = note_id
        self.canvas.focus_set()
        self._highlight()

    def _highlight(self) -> None:
        for note_id, frame in self.cards.items():
            selected = note_id == self.selected_id
            color = "#EFF6FF" if selected else "#FFFFFF"
            frame.configure(
                background=color, highlightbackground="#93C5FD" if selected else "#E2E8F0"
            )
            for child in frame.winfo_children():
                if isinstance(child, tk.Label) and not getattr(child, "_badge", False):
                    child.configure(background=color)

    def clear_selection(self) -> None:
        self.selected_id = None
        self._highlight()

    def render(self, state: ListState) -> None:
        self.heading.configure(text="Thùng rác" if state.mode == "trash" else "Tất cả ghi chú")
        text = (
            "Đang tải…"
            if state.loading
            else "Kiểm tra ngày YYYY-MM-DD, thứ tự ngày và timezone."
            if state.error and state.error.value == "VALIDATION"
            else "Không tải được. Chọn Làm mới để thử lại."
            if state.error
            else f"Đang hiển thị {len(state.items)} ghi chú"
            if state.items
            else "Thùng rác đang trống."
            if state.mode == "trash"
            else "Không có kết quả. Thử xóa bộ lọc hoặc tạo ghi chú."
        )
        self.message.configure(text=text, bootstyle="danger" if state.error else "secondary")
        new_items = {item.note_id: item for item in state.items}
        if new_items != self.items or state.mode != self._mode:
            self.items, self._mode = new_items, state.mode
            for child in self.card_container.winfo_children():
                child.destroy()
            self.cards = {}
            deleted = {row.note.note_id: row.deleted_at for row in state.trash_items}
            for item in state.items:
                card = tk.Frame(
                    self.card_container,
                    autostyle=False,
                    background="#FFFFFF",
                    padx=12,
                    pady=10,
                    highlightthickness=1,
                    highlightbackground="#E2E8F0",
                    cursor="hand2",
                )
                card.pack(fill="x", padx=4, pady=(0, 8))
                self.cards[item.note_id] = card
                badge, foreground, background = PRIORITY_STYLE[item.priority.value]
                priority = tk.Label(
                    card,
                    autostyle=False,
                    text=badge,
                    foreground=foreground,
                    background=background,
                    font=("Segoe UI", 9, "bold"),
                    padx=7,
                    pady=2,
                )
                priority._badge = True
                priority.pack(anchor="w")
                for text, font, color in (
                    (item.title, ("Segoe UI", 11, "bold"), "#172033"),
                    (
                        item.content.replace("\n", " ")[:100] or "Chưa có nội dung",
                        ("Segoe UI", 10),
                        "#475569",
                    ),
                    (
                        deleted.get(item.note_id, item.updated_at)
                        .astimezone()
                        .strftime("%d/%m/%Y  %H:%M"),
                        ("Segoe UI", 9),
                        "#64748B",
                    ),
                ):
                    label = tk.Label(
                        card,
                        autostyle=False,
                        text=text,
                        background="#FFFFFF",
                        foreground=color,
                        font=font,
                        justify="left",
                        anchor="w",
                        wraplength=max(100, self.canvas.winfo_width() - 40),
                    )
                    label._wrap = True
                    label.pack(anchor="w", fill="x", pady=(5, 0))
                for widget in (card, *card.winfo_children()):
                    widget.bind(
                        "<Button-1>", lambda _event, note_id=item.note_id: self._choose(note_id)
                    )
                    widget.bind("<MouseWheel>", self._wheel)
            self._highlight()
        self.more.configure(
            state="normal" if state.next_cursor and not state.loading else "disabled"
        )
