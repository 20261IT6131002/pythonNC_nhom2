"""An OS lease prevents separate processes from writing one draft profile concurrently."""

import os
import sys
from pathlib import Path
from typing import BinaryIO


class ProfileLock:
    def __init__(self, directory: Path) -> None:
        self.path = directory / ".profile.lock"
        self._file: BinaryIO | None = None

    def acquire(self) -> None:
        if self._file is not None:
            return

        descriptor = os.open(
            self.path, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600
        )
        handle = os.fdopen(descriptor, "r+b")

        try:
            if sys.platform == "win32":
                import msvcrt

                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BaseException:
            handle.close()
            raise

        self._file = handle

    def close(self) -> None:
        if self._file is not None:
            self._file.close()
            self._file = None
