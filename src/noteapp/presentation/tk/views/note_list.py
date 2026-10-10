"""Keyboard accessible, paged note cards inspired by the supplied sketch."""

import tkinter as tk
import tkinter.font as tkfont
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
        self._card_pool = []
        self._deleted = {}
        self._priority_font = tkfont.Font(root=self, family="Segoe UI", size=9, weight="bold")
        self._badge_width = (
            max(self._priority_font.measure(value[0]) for value in PRIORITY_STYLE.values()) + 16
        )
        self._canvas_width = None
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
        self.canvas.tag_bind("note-card", "<Button-1>", self._click_card)
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
        if event.width == self._canvas_width:
            return
        self._canvas_width = event.width
        self.message.configure(wraplength=max(100, event.width))
        self._draw_cards()

    def close(self) -> None:
        self.canvas.unbind("<Configure>")

    def _click_card(self, _event) -> None:
        current = self.canvas.find_withtag("current")
        if current:
            for tag in self.canvas.gettags(current[0]):
                if tag.startswith("note-id:"):
                    self._choose(tag.removeprefix("note-id:"))
                    break

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
        bounds = self.canvas.bbox(self.cards[note_id][0])
        top = self.canvas.canvasy(0)
        height = self.canvas.winfo_height()
        total = max(1, float(self.canvas.cget("scrollregion").split()[-1]))
        if bounds[1] < top:
            self.canvas.yview_moveto(max(0, bounds[1]) / total)
        elif bounds[3] > top + height:
            self.canvas.yview_moveto(max(0, bounds[3] - height) / total)

    def _highlight(self) -> None:
        for note_id, objects in self.cards.items():
            selected = note_id == self.selected_id
            self.canvas.itemconfigure(
                objects[0],
                fill="#EFF6FF" if selected else "#FFFFFF",
                outline="#93C5FD" if selected else "#E2E8F0",
            )

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
            self._deleted = {row.note.note_id: row.deleted_at for row in state.trash_items}
            self._draw_cards()
        self.more.configure(
            state="normal" if state.next_cursor and not state.loading else "disabled"
        )

    def _draw_cards(self) -> None:
        # Canvas rows avoid a large widget tree and render only text/geometry.
        # Stable item IDs preserve click/keyboard behavior across filter resets.
        self.cards = {}
        width = max(120, self.canvas.winfo_width() - 12)
        y = 4
        rows = list(self.items.values())
        while len(self._card_pool) < len(self.items):
            objects = (
                self.canvas.create_rectangle(0, 0, 1, 1),
                self.canvas.create_rectangle(0, 0, 1, 1, outline=""),
                self.canvas.create_text(0, 0, anchor="nw", font=self._priority_font),
                self.canvas.create_text(
                    0, 0, anchor="nw", font=("Segoe UI", 11, "bold"), fill="#172033"
                ),
                self.canvas.create_text(0, 0, anchor="nw", font=("Segoe UI", 10), fill="#475569"),
                self.canvas.create_text(0, 0, anchor="nw", font=("Segoe UI", 9), fill="#64748B"),
            )
            self._card_pool.append(objects)
        for index, objects in enumerate(self._card_pool):
            if index >= len(self.items):
                for obj in objects:
                    self.canvas.itemconfigure(obj, state="hidden")
                continue
            item = rows[index]
            self.cards[item.note_id] = objects
            tags = ("note-card", "note-id:" + item.note_id)
            for obj in objects:
                self.canvas.itemconfigure(obj, state="normal", tags=tags)
            badge, foreground, background = PRIORITY_STYLE[item.priority.value]
            self.canvas.itemconfigure(objects[1], fill=background)
            self.canvas.coords(
                objects[1],
                16,
                y + 10,
                16 + self._badge_width,
                y + 18 + self._priority_font.metrics("linespace"),
            )
            self.canvas.itemconfigure(objects[2], text=badge, fill=foreground)
            self.canvas.coords(objects[2], 24, y + 14)
            text_y = y + 30 + self._priority_font.metrics("linespace")
            for obj, text in zip(
                objects[3:],
                (
                    item.title,
                    item.content.replace("\n", " ")[:100] or "Chưa có nội dung",
                    self._deleted.get(item.note_id, item.updated_at)
                    .astimezone()
                    .strftime("%d/%m/%Y  %H:%M"),
                ),
                strict=True,
            ):
                self.canvas.itemconfigure(obj, text=text, width=max(80, width - 32))
                self.canvas.coords(obj, 16, text_y)
                text_y = self.canvas.bbox(obj)[3] + 8
            self.canvas.coords(objects[0], 4, y, width, text_y + 4)
            y = text_y + 16
        self.canvas.configure(scrollregion=(0, 0, width, max(y, 1)))
        self._highlight()
