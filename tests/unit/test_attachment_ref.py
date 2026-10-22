"""P3A-04: attachment value object and size policy are pure."""

import hashlib

import pytest

from noteapp.domain.errors import ImageTooLarge, UnsupportedImage, ValidationError
from noteapp.domain.policies.attachment_policy import (
    INLINE_MAX_BYTES,
    MAX_IMAGE_BYTES,
    sanitize_display_name,
    storage_kind_for,
)
from noteapp.domain.value_objects.attachment_ref import AttachmentRef, StorageKind

DIGEST = hashlib.sha256(b"x").hexdigest()


def ref(**changes):
    values = dict(
        storage_kind="INLINE",
        storage_key="a" * 24,
        mime_type="image/png",
        size_bytes=10,
        sha256=DIGEST,
        display_name="photo.png",
    )
    return AttachmentRef(**{**values, **changes})


@pytest.mark.parametrize(
    ("size", "kind"),
    [
        (1, "INLINE"),
        (INLINE_MAX_BYTES, "INLINE"),
        (INLINE_MAX_BYTES + 1, "GRIDFS"),
        (MAX_IMAGE_BYTES, "GRIDFS"),
    ],
)
def test_size_boundaries(size, kind):
    assert storage_kind_for(size) == kind


@pytest.mark.parametrize("size", [0, -1, True, 1.5, None])
def test_invalid_sizes_are_validation_errors(size):
    with pytest.raises(ValidationError):
        storage_kind_for(size)


def test_over_ten_mib_is_rejected():
    with pytest.raises(ImageTooLarge):
        storage_kind_for(MAX_IMAGE_BYTES + 1)


def test_valid_ref_is_immutable_and_normalizes_kind():
    value = ref()
    assert value.storage_kind is StorageKind.INLINE
    with pytest.raises(AttributeError):
        value.storage_key = "b"


@pytest.mark.parametrize(
    "changes",
    [
        {"storage_kind": "S3"},
        {"storage_key": ""},
        {"storage_key": "a b"},
        {"storage_key": "k" * 65},
        {"storage_key": "ключ"},
        {"sha256": "ABC"},
        {"sha256": DIGEST.upper()},
        {"size_bytes": INLINE_MAX_BYTES + 1},  # INLINE kind with GridFS-sized payload
        {"storage_kind": "GRIDFS", "size_bytes": 10},
    ],
)
def test_inconsistent_refs_are_rejected(changes):
    with pytest.raises(ValidationError):
        ref(**changes)


def test_unsupported_mime_is_rejected():
    with pytest.raises(UnsupportedImage):
        ref(mime_type="image/svg+xml")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("../../etc/passwd", "passwd"),
        ("C:\\Users\\me\\cat.png", "cat.png"),
        ("  ảnh đẹp.png  ", "ảnh đẹp.png"),
        ("bad\x00name\n.png", "badname.png"),
        ("...", "image"),
        ("", "image"),
        (None, "image"),
        ("x" * 500, "x" * 120),
    ],
)
def test_display_name_is_a_label_never_a_path(raw, expected):
    assert sanitize_display_name(raw) == expected
    assert ref(display_name=raw).display_name == expected
