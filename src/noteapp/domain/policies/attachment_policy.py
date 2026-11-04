"""Pure image attachment rules: format allowlist, size boundary and display names."""

import re
import unicodedata

from noteapp.domain.errors import ImageTooLarge, UnsupportedImage, ValidationError

INLINE_MAX_BYTES = 1024 * 1024
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_IMAGE_PIXELS = 25_000_000
MAX_IMAGE_SIDE = 12_000
THUMBNAIL_MAX_WIDTH = 400
ALLOWED_MIME_TYPES = ("image/png", "image/jpeg", "image/gif", "image/webp")
DISPLAY_NAME_LIMIT = 120
DEFAULT_DISPLAY_NAME = "image"


def validate_mime_type(mime_type: str) -> str:
    if mime_type not in ALLOWED_MIME_TYPES:
        raise UnsupportedImage("Only PNG, JPEG, GIF and WebP images are supported.")
    return mime_type


def storage_kind_for(size_bytes: int) -> str:
    """Return INLINE for <= 1 MiB, GRIDFS up to 10 MiB inclusive, else reject."""
    if type(size_bytes) is not int or size_bytes < 1:
        raise ValidationError("Image size must be a positive integer.")
    if size_bytes > MAX_IMAGE_BYTES:
        raise ImageTooLarge("Images larger than 10 MiB are not accepted.")
    return "INLINE" if size_bytes <= INLINE_MAX_BYTES else "GRIDFS"


def sanitize_display_name(name: object) -> str:
    """Label only: drop directories and control characters; never used as a path."""
    if not isinstance(name, str):
        return DEFAULT_DISPLAY_NAME
    leaf = re.split(r"[\\/]", unicodedata.normalize("NFC", name))[-1]
    cleaned = "".join(ch for ch in leaf if unicodedata.category(ch)[0] != "C").strip(" .")
    return cleaned[:DISPLAY_NAME_LIMIT] or DEFAULT_DISPLAY_NAME
