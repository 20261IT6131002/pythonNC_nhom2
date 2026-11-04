"""Deterministic attachment ports for core tests: no Pillow, Mongo or display."""

import hashlib

from noteapp.application.ports.image_processor import Thumbnail, ValidatedImage
from noteapp.domain.errors import AttachmentStoreFailure, CorruptedImage, UnsupportedImage
from noteapp.domain.policies.attachment_policy import storage_kind_for
from noteapp.domain.value_objects.attachment_ref import AttachmentRef, StorageKind


class FakeImageProcessor:
    """b'BAD…' is corrupt, b'TXT…' unsupported, anything else a 10x5 PNG."""

    def inspect(self, data):
        if data.startswith(b"BAD"):
            raise CorruptedImage("corrupt")
        if data.startswith(b"TXT"):
            raise UnsupportedImage("unsupported")
        return ValidatedImage(data, "image/png", hashlib.sha256(data).hexdigest(), 10, 5)

    def thumbnail(self, data, max_width):
        return Thumbnail(b"PNG:" + data[:8], min(10, max_width), 5)


class FakeAttachmentStore:
    def __init__(self):
        self.blobs = {}
        self.counter = 0
        self.fail_put = self.fail_delete = self.fail_get = None

    def put(self, owner_note_id, image, display_name):
        if self.fail_put is not None:
            raise self.fail_put
        self.counter += 1
        key = f"{self.counter:024x}"
        self.blobs[key] = image.data
        return AttachmentRef(
            StorageKind(storage_kind_for(len(image.data))),
            key,
            image.mime_type,
            len(image.data),
            image.sha256,
            display_name,
        )

    def get(self, ref):
        if self.fail_get is not None:
            raise self.fail_get
        if ref.storage_key not in self.blobs:
            raise AttachmentStoreFailure("missing")
        return self.blobs[ref.storage_key]

    def delete(self, ref):
        if self.fail_delete is not None:
            raise self.fail_delete
        self.blobs.pop(ref.storage_key, None)

    def exists(self, ref):
        return ref.storage_key in self.blobs
