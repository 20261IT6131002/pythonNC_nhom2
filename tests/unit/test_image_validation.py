"""P3A-05: real Pillow validation and thumbnails (no Mongo, no display)."""

import hashlib
from io import BytesIO

import pytest
from PIL import Image

from noteapp.domain.errors import CorruptedImage, ImageTooLarge, UnsupportedImage, ValidationError
from noteapp.domain.policies.attachment_policy import MAX_IMAGE_BYTES
from noteapp.infrastructure.attachment.image_validator import PillowImageProcessor

processor = PillowImageProcessor()


def encoded(fmt, size=(40, 20), mode="RGB", **options):
    out = BytesIO()
    Image.new(mode, size, (200, 30, 30) if mode == "RGB" else 0).save(out, format=fmt, **options)
    return out.getvalue()


@pytest.mark.parametrize(
    ("fmt", "mime"),
    [
        ("PNG", "image/png"),
        ("JPEG", "image/jpeg"),
        ("GIF", "image/gif"),
        ("WEBP", "image/webp"),
    ],
)
def test_allowed_formats_are_detected_from_content(fmt, mime):
    data = encoded(fmt)
    image = processor.inspect(data)
    assert (image.mime_type, image.width, image.height) == (mime, 40, 20)
    assert image.sha256 == hashlib.sha256(data).hexdigest() and image.data == data


def test_format_comes_from_bytes_not_from_a_claimed_extension():
    # A JPEG named .png is still JPEG; the processor never sees a file name.
    assert processor.inspect(encoded("JPEG")).mime_type == "image/jpeg"


@pytest.mark.parametrize(
    "payload",
    [
        b"<svg xmlns='http://www.w3.org/2000/svg'></svg>",
        b"%PDF-1.7 not an image",
        b"plain text pretending to be a photo",
        encoded("BMP"),
        encoded("TIFF"),
    ],
)
def test_other_formats_are_unsupported(payload):
    with pytest.raises(UnsupportedImage):
        processor.inspect(payload)


@pytest.mark.parametrize("payload", [b"", b"\x89PNG\r\n\x1a\n"])
def test_empty_or_header_only_payloads_are_rejected(payload):
    with pytest.raises((CorruptedImage, UnsupportedImage)):
        processor.inspect(payload)


def test_truncated_image_is_corrupt():
    data = encoded("PNG", size=(300, 300))
    with pytest.raises(CorruptedImage):
        processor.inspect(data[: len(data) // 2])


def test_flipped_bytes_in_pixel_data_are_corrupt_or_rejected():
    data = bytearray(encoded("PNG", size=(300, 300)))
    for index in range(len(data) // 2, len(data) // 2 + 64):
        data[index] ^= 0xFF
    with pytest.raises(CorruptedImage):
        processor.inspect(bytes(data))


def test_pixel_bomb_is_rejected_by_header_before_decoding():
    # ~26 MP of one colour compresses to a few KB; it must still be refused.
    bomb = encoded("PNG", size=(5200, 5000), mode="L")
    assert len(bomb) < 1024 * 1024
    with pytest.raises(ImageTooLarge):
        processor.inspect(bomb)


def test_excessive_single_side_is_rejected():
    with pytest.raises(ImageTooLarge):
        processor.inspect(encoded("PNG", size=(12001, 1), mode="L"))


def test_over_ten_mib_bytes_are_rejected():
    with pytest.raises(ImageTooLarge):
        processor.inspect(b"\x00" * (MAX_IMAGE_BYTES + 1))


def test_thumbnail_is_at_most_400_wide_keeps_ratio_and_is_png():
    data = encoded("JPEG", size=(1000, 500))
    original = bytes(data)
    thumb = processor.thumbnail(data, 400)
    assert (thumb.width, thumb.height) == (400, 200)
    decoded = Image.open(BytesIO(thumb.png))
    assert decoded.format == "PNG" and decoded.size == (400, 200)
    assert data == original  # source bytes are never mutated


def test_small_images_are_not_upscaled():
    thumb = processor.thumbnail(encoded("PNG", size=(120, 60)), 400)
    assert (thumb.width, thumb.height) == (120, 60)


def test_thumbnail_handles_palette_and_alpha_modes():
    palette = encoded("GIF", size=(800, 400))
    assert processor.thumbnail(palette, 400).width == 400
    alpha = encoded("PNG", size=(500, 500), mode="RGBA")
    assert Image.open(BytesIO(processor.thumbnail(alpha, 250).png)).size == (250, 250)


def test_thumbnail_of_garbage_is_corrupt_and_width_is_validated():
    with pytest.raises(CorruptedImage):
        processor.thumbnail(b"not an image", 400)
    with pytest.raises(ValidationError):
        processor.thumbnail(encoded("PNG"), 0)
