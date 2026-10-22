"""P3A-06: shared store contract against real Mongo (BinData inline + GridFS)."""

import pytest

from noteapp.domain.errors import AttachmentStoreFailure
from noteapp.domain.policies.attachment_policy import INLINE_MAX_BYTES
from noteapp.infrastructure.attachment.hybrid_store import MongoAttachmentStore
from tests.attachment_contracts import AttachmentStoreContract, image

pytestmark = pytest.mark.integration


@pytest.fixture
def store(mongo_database):
    return MongoAttachmentStore(mongo_database[0])


class TestMongoAttachmentStore(AttachmentStoreContract):
    """Run the shared behavior against the concrete adapter, without mocks."""


def test_inline_lives_in_blob_collection_and_large_in_gridfs(mongo_database, store):
    database = mongo_database[0]
    small = store.put("a" * 24, image(INLINE_MAX_BYTES), "s.png")
    large = store.put("a" * 24, image(INLINE_MAX_BYTES + 1), "l.png")
    assert database.attachment_blobs.count_documents({}) == 1
    assert database["attachments.files"].count_documents({}) == 1
    assert database["attachments.files"].find_one()["metadata"]["owner_note_id"] == "a" * 24
    assert database.notes.count_documents({}) == 0  # payloads never touch note documents
    store.delete(small)
    store.delete(large)
    assert database.attachment_blobs.count_documents({}) == 0
    assert database["attachments.files"].count_documents({}) == 0
    assert database["attachments.chunks"].count_documents({}) == 0


def test_invalid_key_is_a_store_failure_not_a_crash(store):
    from noteapp.domain.value_objects.attachment_ref import AttachmentRef

    ref = AttachmentRef("INLINE", "not-an-object-id", "image/png", 3, "0" * 64, "x.png")
    with pytest.raises(AttachmentStoreFailure):
        store.get(ref)
    with pytest.raises(AttachmentStoreFailure):
        store.delete(ref)
