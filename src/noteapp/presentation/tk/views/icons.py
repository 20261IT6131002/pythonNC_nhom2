"""Original Material Icons: bytes load on startup worker, PhotoImages on Tk owner."""

import base64
import tkinter as tk
from pathlib import Path


def load_icon_data() -> dict[str, str]:
    directory = Path(__file__).resolve().parents[1] / "assets/icons"
    return {
        path.stem: base64.b64encode(path.read_bytes()).decode("ascii")
        for path in directory.glob("*.png")
    }


def create_icons(master: tk.Misc, data: dict[str, str]) -> dict[str, tk.PhotoImage]:
    return {name: tk.PhotoImage(master=master, data=png).subsample(2) for name, png in data.items()}
