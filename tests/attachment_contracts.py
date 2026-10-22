"""Adapter-neutral AttachmentStore behavior shared by the fake and the Mongo adapter."""

import hashlib

import pytest

from noteapp.application.ports.image_processor import ValidatedImage
from noteapp.domain.errors import AttachmentStoreFailure, ImageTooLarge
from noteapp.domain.policies.attachment_policy import INLINE_MAX_BYTES, MAX_IMAGE_BYTES
from noteapp.domain.value_objects.attachment_ref import AttachmentRef, StorageKind


def image(size, fill=b"a"):
    data = (fill * size)[:size]
    return ValidatedImage(data, "image/png", hashlib.sha256(data).hexdigest(), 1, 1)


class AttachmentStoreContract:
    """Concrete classes provide a fresh `store` fixture."""

    @pytest.mark.parametrize(
        ("size", "kind"),
        [
            (1, StorageKind.INLINE),
            (INLINE_MAX_BYTES, StorageKind.INLINE),
            (INLINE_MAX_BYTES + 1, StorageKind.GRIDFS),
            (MAX_IMAGE_BYTES, StorageKind.GRIDFS),
        ],
    )
    def test_boundary_picks_storage_kind_and_roundtrips(self, store, size, kind):
        payload = image(size)
        ref = store.put("a" * 24, payload, "photo.png")
        assert isinstance(ref, AttachmentRef) and ref.storage_kind is kind
        assert ref.size_bytes == size and ref.sha256 == payload.sha256
        assert store.exists(ref)
        assert store.get(ref) == payload.data

    def test_over_ten_mib_is_rejected_without_storing(self, store):
        with pytest.raises(ImageTooLarge):
            store.put("a" * 24, image(MAX_IMAGE_BYTES + 1), "huge.png")

    def test_delete_is_idempotent_and_removes_payload(self, store):
        ref = store.put("a" * 24, image(100), "x.png")
        store.delete(ref)
        store.delete(ref)
        assert not store.exists(ref)
        with pytest.raises(AttachmentStoreFailure):
            store.get(ref)

    def test_keys_are_unique_and_opaque(self, store):
        first = store.put("a" * 24, image(10), "x.png")
        second = store.put("a" * 24, image(10), "x.png")
        assert first.storage_key != second.storage_key
        assert store.get(first) == store.get(second)

    def test_display_name_is_only_a_label(self, store):
        ref = store.put("a" * 24, image(10), "../../evil\x00.png")
        assert ref.display_name == "evil.png"
        assert "evil" not in ref.storage_key
