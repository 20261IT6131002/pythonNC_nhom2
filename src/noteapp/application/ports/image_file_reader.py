"""Reads a user-selected image file; the filesystem adapter lives in infrastructure."""

from typing import Protocol, runtime_checkable


@runtime_checkable
class ImageFileReader(Protocol):
    def read(self, path: str) -> tuple[bytes, str]:
        """Return (bytes, display name) for a regular file of at most 10 MiB.

        Raises ImageTooLarge before reading an oversized file and ValidationError when the
        path is not a readable regular file. The name is a label, never a trusted path.
        """
