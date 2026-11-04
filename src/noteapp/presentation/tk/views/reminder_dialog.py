"""Modal date/time entry. Returns naive local wall-clock time; the core converts to UTC."""

import tkinter as tk
from datetime import datetime, timedelta
from tkinter import simpledialog

import ttkbootstrap as ttk

DATE_FORMAT = "%d/%m/%Y"
TIME_FORMAT = "%H:%M"


def parse_local_datetime(date_text: str, time_text: str) -> datetime:
    """Raise ValueError on anything that is not dd/mm/yyyy and HH:MM."""
    return datetime.strptime(
        date_text.strip() + " " + time_text.strip(), f"{DATE_FORMAT} {TIME_FORMAT}"
    )


def default_reminder_time() -> datetime:
    return (datetime.now() + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)


class ReminderDialog(simpledialog.Dialog):
    def __init__(self, parent: tk.Misc, initial: datetime | None = None) -> None:
        self._initial = initial or default_reminder_time()
        self.result: datetime | None = None
        super().__init__(parent, "Đặt nhắc nhở")

    def body(self, master: tk.Misc):
        ttk.Label(master, text="Ngày (dd/mm/yyyy)").grid(row=0, column=0, sticky="w")
        ttk.Label(master, text="Giờ (HH:MM, 24 giờ)").grid(row=1, column=0, sticky="w", pady=8)
        self.date = tk.StringVar(value=self._initial.strftime(DATE_FORMAT))
        self.time = tk.StringVar(value=self._initial.strftime(TIME_FORMAT))
        self.date_entry = ttk.Entry(master, textvariable=self.date, width=14)
        self.time_entry = ttk.Entry(master, textvariable=self.time, width=14)
        self.date_entry.grid(row=0, column=1, padx=(12, 0))
        self.time_entry.grid(row=1, column=1, padx=(12, 0), pady=8)
        self.message = ttk.Label(master, text="", bootstyle="danger")
        self.message.grid(row=2, column=0, columnspan=2, sticky="w")
        return self.date_entry

    def validate(self) -> bool:
        try:
            self._value = parse_local_datetime(self.date.get(), self.time.get())
        except ValueError:
            self.message.configure(text="Nhập ngày dd/mm/yyyy và giờ HH:MM hợp lệ.")
            return False
        return True

    def apply(self) -> None:
        self.result = self._value


def ask_reminder_time(parent: tk.Misc, initial: datetime | None = None) -> datetime | None:
    return ReminderDialog(parent, initial).result
