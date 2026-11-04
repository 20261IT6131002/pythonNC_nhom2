"""Untrusted image validation: size, real decode, format allowlist and pixel guards."""

import hashlib
import warnings
from io import BytesIO

from PIL import Image

from noteapp.application.ports.image_processor import Thumbnail, ValidatedImage
from noteapp.domain.errors import CorruptedImage, ImageTooLarge, UnsupportedImage
from noteapp.domain.policies.attachment_policy import (
    MAX_IMAGE_BYTES,
    MAX_IMAGE_PIXELS,
    MAX_IMAGE_SIDE,
)
from noteapp.infrastructure.attachment.thumbnailer import make_thumbnail

FORMAT_MIME = {
    "PNG": "image/png",
    "JPEG": "image/jpeg",
    "GIF": "image/gif",
    "WEBP": "image/webp",
}


class PillowImageProcessor:
    def inspect(self, data: bytes) -> ValidatedImage:
        if not isinstance(data, bytes) or not data:
            raise CorruptedImage("The image is empty.")
        if len(data) > MAX_IMAGE_BYTES:
            raise ImageTooLarge("Images larger than 10 MiB are not accepted.")
        try:
            # Escalate Pillow's own bomb warning so it is rejected, never merely logged.
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(BytesIO(data), formats=tuple(FORMAT_MIME)) as probe:
                    mime = FORMAT_MIME[probe.format]
                    width, height = probe.size
                    if (
                        width < 1
                        or height < 1
                        or width > MAX_IMAGE_SIDE
                        or height > MAX_IMAGE_SIDE
                        or width * height > MAX_IMAGE_PIXELS
                    ):
                        raise ImageTooLarge("The image dimensions are too large.")
                    probe.verify()
                with Image.open(BytesIO(data), formats=tuple(FORMAT_MIME)) as decoded:
                    decoded.load()  # detects truncated pixel data that verify() can miss
        except Image.UnidentifiedImageError:
            raise UnsupportedImage("Only PNG, JPEG, GIF and WebP images are supported.") from None
        except (ImageTooLarge, UnsupportedImage):
            raise
        except (
            OSError,
            ValueError,
            SyntaxError,
            EOFError,
            Image.DecompressionBombError,
            Image.DecompressionBombWarning,
        ):
            raise CorruptedImage("The image could not be decoded.") from None
        return ValidatedImage(data, mime, hashlib.sha256(data).hexdigest(), width, height)

    def thumbnail(self, data: bytes, max_width: int) -> Thumbnail:
        return make_thumbnail(data, max_width)
