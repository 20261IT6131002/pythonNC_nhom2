"""Image decoding port; the Pillow implementation lives in infrastructure."""

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class ValidatedImage:
    data: bytes
    mime_type: str
    sha256: str
    width: int
    height: int


@dataclass(frozen=True)
class Thumbnail:
    png: bytes
    width: int
    height: int


@runtime_checkable
class ImageProcessor(Protocol):
    def inspect(self, data: bytes) -> ValidatedImage:
        """Decode-verify untrusted bytes.

        Raises ImageTooLarge (size/pixels), UnsupportedImage (format) or CorruptedImage.
        The detected format, never a file extension, decides the MIME type.
        """

    def thumbnail(self, data: bytes, max_width: int) -> Thumbnail:
        """Return a PNG no wider than max_width, keeping aspect ratio; input is untouched."""
