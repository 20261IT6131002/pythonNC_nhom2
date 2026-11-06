"""Local persistence is independent from the editor's remote save phase."""

from enum import Enum


class SyncState(str, Enum):
    REMOTE = "REMOTE"
    LOCAL_PENDING = "LOCAL_PENDING"
    LOCAL_SAVED = "LOCAL_SAVED"
    OFFLINE = "OFFLINE"
    RECOVERY_AVAILABLE = "RECOVERY_AVAILABLE"
    SECURE_AUTOSAVE_DISABLED = "SECURE_AUTOSAVE_DISABLED"
