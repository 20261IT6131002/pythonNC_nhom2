"""P3A-07: note image lifecycle invariants with fault injection, no Mongo or display."""

import pytest

from noteapp.application.dto.note_input import (
    AttachImageFileInput,
    AttachImageInput,
    GetImageInput,
    RemoveImageInput,
)
from noteapp.application.services.attachment_service import AttachmentService
from noteapp.domain.errors import (
    AttachmentStoreFailure,
    Conflict,
    CorruptedImage,
    ImageTooLarge,
    NotFound,
    RepositoryUnavailable,
    UnsupportedImage,
    ValidationError,
)
from noteapp.domain.policies.attachment_policy import INLINE_MAX_BYTES, MAX_IMAGE_BYTES
from tests.attachment_fakes import FakeAttachmentStore, FakeImageProcessor
from tests.fakes import FakeClock, FakeNotesWithAttachments
from tests.repository_contracts import note


@pytest.fixture
def world():
    notes, store = FakeNotesWithAttachments(), FakeAttachmentStore()
    service = AttachmentService(notes, notes, store, FakeImageProcessor(), FakeClock())
    saved = notes.create(note(), "11111111-1111-4111-8111-111111111111")
    return notes, store, service, saved


def attach(service, saved, data=b"image-one", version=None, name="a.png"):
    return service.attach(AttachImageInput(saved.id, version or saved.version, data, name))


def test_attach_stores_payload_then_references_it(world):
    notes, store, service, saved = world
    view = attach(service, saved)
    assert view.version == saved.version + 1
    assert view.attachment.kind == "INLINE" and view.attachment.display_name == "a.png"
    assert len(store.blobs) == 1
    assert notes.find_by_id(saved.id).attachment.storage_key in store.blobs


def test_inline_gridfs_boundary(world):
    _, _, service, saved = world
    small = attach(service, saved, b"x" * INLINE_MAX_BYTES)
    large = service.attach(
        AttachImageInput(saved.id, small.version, b"x" * (INLINE_MAX_BYTES + 1), "big.png")
    )
    assert (small.attachment.kind, large.attachment.kind) == ("INLINE", "GRIDFS")


def test_over_ten_mib_is_rejected_before_any_io(world):
    notes, store, service, saved = world
    with pytest.raises(ImageTooLarge):
        attach(service, saved, b"x" * (MAX_IMAGE_BYTES + 1))
    assert store.blobs == {} and notes.find_by_id(saved.id) == saved


@pytest.mark.parametrize(("data", "error"), [(b"BAD", CorruptedImage), (b"TXT", UnsupportedImage)])
def test_invalid_images_keep_note_and_old_image(world, data, error):
    notes, store, service, saved = world
    first = attach(service, saved)
    before = notes.find_by_id(saved.id)
    with pytest.raises(error):
        attach(service, saved, data, version=first.version)
    assert notes.find_by_id(saved.id) == before
    assert len(store.blobs) == 1


def test_replace_deletes_old_only_after_swap(world):
    notes, store, service, saved = world
    first = attach(service, saved, b"first")
    old_key = notes.find_by_id(saved.id).attachment.storage_key
    second = service.attach(AttachImageInput(saved.id, first.version, b"second", "b.png"))
    new_key = notes.find_by_id(saved.id).attachment.storage_key
    assert second.version == first.version + 1 and old_key != new_key
    assert list(store.blobs) == [new_key]


def test_replace_cas_failure_deletes_new_and_retains_old(world):
    notes, store, service, saved = world
    first = attach(service, saved, b"first")
    old = notes.find_by_id(saved.id).attachment
    with pytest.raises(Conflict):
        service.attach(AttachImageInput(saved.id, first.version - 1, b"second", "b.png"))
    assert notes.find_by_id(saved.id).attachment == old
    assert list(store.blobs) == [old.storage_key]


def test_note_update_exception_after_upload_cleans_new_upload(world):
    notes, store, service, saved = world
    first = attach(service, saved, b"first")
    old = notes.find_by_id(saved.id).attachment
    notes.fail_link = RepositoryUnavailable("down")
    with pytest.raises(RepositoryUnavailable):
        service.attach(AttachImageInput(saved.id, first.version, b"second", "b.png"))
    assert list(store.blobs) == [old.storage_key]


def test_store_put_failure_leaves_note_untouched(world):
    notes, store, service, saved = world
    store.fail_put = AttachmentStoreFailure("down")
    with pytest.raises(AttachmentStoreFailure):
        attach(service, saved)
    assert notes.find_by_id(saved.id) == saved and store.blobs == {}


def test_delete_old_failure_does_not_fail_the_replace(world):
    notes, store, service, saved = world
    first = attach(service, saved, b"first")
    store.fail_delete = AttachmentStoreFailure("down")
    second = service.attach(AttachImageInput(saved.id, first.version, b"second", "b.png"))
    assert second.attachment is not None
    assert len(store.blobs) == 2  # old payload is unreferenced, left to the reconciler


def test_stale_version_and_missing_note(world):
    _, store, service, saved = world
    with pytest.raises(Conflict):
        attach(service, saved, version=saved.version + 1)
    with pytest.raises(NotFound):
        service.attach(AttachImageInput("f" * 24, 1, b"x", "x.png"))
    assert store.blobs == {}


def test_attach_does_not_overwrite_text(world):
    notes, _, service, saved = world
    attach(service, saved)
    after = notes.find_by_id(saved.id)
    assert (after.title, after.content, after.priority) == (
        saved.title,
        saved.content,
        saved.priority,
    )


def test_remove_clears_reference_then_deletes_payload(world):
    notes, store, service, saved = world
    first = attach(service, saved)
    removed = service.remove(RemoveImageInput(saved.id, first.version))
    assert removed.attachment is None and removed.version == first.version + 1
    assert store.blobs == {} and notes.find_by_id(saved.id).attachment is None
    assert service.remove(RemoveImageInput(saved.id, removed.version)).version == removed.version


def test_remove_stale_version_keeps_image(world):
    notes, store, service, saved = world
    first = attach(service, saved)
    with pytest.raises(Conflict):
        service.remove(RemoveImageInput(saved.id, first.version - 1))
    assert notes.find_by_id(saved.id).attachment is not None and len(store.blobs) == 1


def test_get_returns_thumbnail_and_verifies_integrity(world):
    _, store, service, saved = world
    view = attach(service, saved, b"payload-bytes")
    content = service.get(GetImageInput(saved.id, 400))
    assert content.png.startswith(b"PNG:") and content.display_name == "a.png"
    key = next(iter(store.blobs))
    store.blobs[key] = b"tampered"
    with pytest.raises(AttachmentStoreFailure):
        service.get(GetImageInput(saved.id, 400))
    assert view.attachment is not None


@pytest.mark.parametrize("width", [0, 401, True, "400", None])
def test_get_rejects_bad_width(world, width):
    _, _, service, saved = world
    attach(service, saved)
    with pytest.raises(ValidationError):
        service.get(GetImageInput(saved.id, width))


def test_get_without_image_is_not_found(world):
    _, _, service, saved = world
    with pytest.raises(NotFound):
        service.get(GetImageInput(saved.id, 400))


def test_non_bytes_payload_is_rejected(world):
    _, _, service, saved = world
    with pytest.raises(ValidationError):
        service.attach(AttachImageInput(saved.id, saved.version, "text", "x.png"))


class FakeFiles:
    def __init__(self, data=b"file-bytes", name="pic.png"):
        self.data, self.name, self.paths = data, name, []

    def read(self, path):
        self.paths.append(path)
        return self.data, self.name


def test_attach_from_file_reads_then_attaches(world):
    notes, store, service, saved = world
    service.files = FakeFiles()
    view = service.attach_from_file(AttachImageFileInput(saved.id, saved.version, "/tmp/pic.png"))
    assert view.attachment.display_name == "pic.png" and len(store.blobs) == 1
    assert service.files.paths == ["/tmp/pic.png"]


def test_attach_from_file_requires_a_reader_and_valid_ids(world):
    _, _, service, saved = world
    with pytest.raises(ValidationError):
        service.attach_from_file(AttachImageFileInput(saved.id, saved.version, "x.png"))
    service.files = FakeFiles()
    with pytest.raises(ValidationError):
        service.attach_from_file(AttachImageFileInput("", saved.version, "x.png"))
