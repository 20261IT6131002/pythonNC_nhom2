"""Read-only distribution chart with exact counts and accessible labels."""

from tkinter import Misc

import ttkbootstrap as ttk

from noteapp.application.queries.note_statistics import NoteStatistics
from noteapp.presentation.tk.views.note_editor import PRIORITIES


class StatisticsDialog(ttk.Toplevel):
    def __init__(self, parent: Misc, statistics: NoteStatistics) -> None:
        super().__init__(title="Phân bố ghi chú", transient=parent, minsize=(450, 310))
        panel = ttk.Frame(self, padding=18)
        panel.pack(fill="both", expand=True)
        ttk.Label(panel, text=f"Ghi chú đang hoạt động: {statistics.total}").pack(anchor="w")
        if not statistics.total:
            ttk.Label(panel, text="Chưa có ghi chú đang hoạt động.").pack(anchor="w", pady=12)
        priority_labels = {value: label for label, value in PRIORITIES.items()}
        self._distribution(
            panel,
            "Theo mức ưu tiên",
            [(priority_labels[priority], count) for priority, count in statistics.priorities],
            statistics.total,
        )
        self._distribution(
            panel,
            "Theo danh mục",
            [(category.label, category.count) for category in statistics.categories],
            statistics.total,
        )
        ttk.Button(panel, text="Đóng", command=self.destroy).pack(anchor="e", pady=(12, 0))

    @staticmethod
    def _distribution(parent, title: str, rows: list[tuple[str, int]], total: int) -> None:
        ttk.Label(parent, text=title, font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(10, 4))
        group = ttk.Frame(parent)
        group.pack(fill="x")
        table = ttk.Treeview(
            group,
            columns=("label", "count", "share"),
            show="headings",
            height=max(1, min(len(rows), 7)),
        )
        for column, label, width in (
            ("label", "Nhóm", 210),
            ("count", "Số ghi chú", 85),
            ("share", "Tỷ trọng", 100),
        ):
            table.heading(column, text=label)
            table.column(column, width=width, anchor="w")
        table.pack(side="left", fill="x", expand=True)
        scrollbar = ttk.Scrollbar(group, orient="vertical", command=table.yview)
        scrollbar.pack(side="right", fill="y")
        table.configure(yscrollcommand=scrollbar.set)
        for label, count in rows:
            share = count / total if total else 0
            bar = "█" * round(share * 10)
            table.insert("", "end", values=(label, count, f"{bar} {share:.0%}".strip()))
