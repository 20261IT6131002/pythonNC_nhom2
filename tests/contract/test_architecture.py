"""P1-AC02: enforce imports and reject deliberately invalid samples."""

import ast
import importlib
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2] / "src" / "noteapp"


def forbidden_imports(source: str, layer: str, package: str) -> list[str]:
    tree = ast.parse(source)
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            name = node.module or ""
            if node.level:
                name = importlib.util.resolve_name("." * node.level + name, package)
            imported.append(name)
    forbidden = {
        "domain": (
            "noteapp.application",
            "noteapp.infrastructure",
            "noteapp.presentation",
            "tkinter",
            "ttkbootstrap",
            "pymongo",
            "bson",
            "gridfs",
            "PIL",
            "plyer",
        ),
        "application": (
            "noteapp.infrastructure",
            "noteapp.presentation",
            "tkinter",
            "ttkbootstrap",
            "pymongo",
            "bson",
            "gridfs",
            "PIL",
            "plyer",
        ),
        "presentation": (
            "noteapp.infrastructure",
            "noteapp.domain",
            "noteapp.application.ports",
            "pymongo",
            "bson",
            "gridfs",
        ),
        "infrastructure": ("noteapp.presentation", "tkinter", "ttkbootstrap"),
    }[layer]
    return [
        name
        for name in imported
        if any(name == prefix or name.startswith(prefix + ".") for prefix in forbidden)
    ]


@pytest.mark.parametrize("layer", ["domain", "application", "presentation", "infrastructure"])
def test_layer_import_boundaries(layer):
    for path in (ROOT / layer).rglob("*.py"):
        module = ".".join(path.relative_to(ROOT.parent).with_suffix("").parts)
        package = module if path.name == "__init__.py" else module.rsplit(".", 1)[0]
        assert not forbidden_imports(path.read_text(encoding="utf-8"), layer, package), path


@pytest.mark.parametrize(
    ("source", "layer", "package"),
    [
        ("import pymongo", "domain", "noteapp.domain"),
        (
            "from noteapp.infrastructure.mongo import repositories",
            "application",
            "noteapp.application",
        ),
        ("from ..infrastructure import config", "application", "noteapp.application"),
        (
            "from noteapp.application.ports.note_repository import NoteRepository",
            "presentation",
            "noteapp.presentation.tk",
        ),
        ("import tkinter", "infrastructure", "noteapp.infrastructure"),
    ],
)
def test_negative_samples_are_rejected(source, layer, package):
    assert forbidden_imports(source, layer, package)


def test_core_imports_do_not_require_gui_or_database():
    for layer in ("domain", "application"):
        for path in (ROOT / layer).rglob("*.py"):
            parts = list(path.relative_to(ROOT.parent).with_suffix("").parts)
            if parts[-1] == "__init__":
                parts.pop()
            importlib.import_module(".".join(parts))
