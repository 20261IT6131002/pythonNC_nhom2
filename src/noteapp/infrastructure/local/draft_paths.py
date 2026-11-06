"""Pure path selection; existence checks and directory creation belong to worker adapters."""

import hashlib
import os
import sys
from pathlib import Path


def draft_directory(db_name: str, override: str | None = None) -> Path:
    if override:
        return Path(override)

    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData/Local")))
    elif sys.platform == "darwin":
        base = Path.home() / "Library/Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share")))

    profile = hashlib.sha256(db_name.encode()).hexdigest()[:24]
    return base / "NoteApp" / "drafts" / profile


def draft_key_name(directory: Path) -> str:
    normalized = os.path.normcase(os.path.abspath(str(directory)))
    profile = hashlib.sha256(normalized.encode()).hexdigest()[:24]
    return "draft-master-key.v1:" + profile
