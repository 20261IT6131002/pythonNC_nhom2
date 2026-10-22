"""Thumbnail generation; never mutates the original bytes."""

from io import BytesIO

from PIL import Image, ImageOps

from noteapp.application.ports.image_processor import Thumbnail
from noteapp.domain.errors import CorruptedImage, ValidationError


def make_thumbnail(data: bytes, max_width: int) -> Thumbnail:
    if type(max_width) is not int or max_width < 1:
        raise ValidationError("Thumbnail width must be a positive integer.")
    try:
        with Image.open(BytesIO(data)) as source:
            image = ImageOps.exif_transpose(source)
            image.load()
            if image.mode not in ("RGB", "RGBA"):
                image = image.convert(
                    "RGBA" if "A" in image.getbands() or "transparency" in image.info else "RGB"
                )
            width, height = image.size
            if width > max_width:
                height = max(1, round(height * max_width / width))
                width = max_width
                image = image.resize((width, height), Image.Resampling.LANCZOS)
            out = BytesIO()
            image.save(out, format="PNG")
    except (OSError, ValueError, SyntaxError, Image.DecompressionBombError):
        raise CorruptedImage("The image could not be decoded.") from None
    return Thumbnail(out.getvalue(), width, height)
