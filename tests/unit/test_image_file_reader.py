"""P3A-05: the file reader guards size and file type before reading."""

import os

import pytest

from noteapp.domain.errors import ImageTooLarge, ValidationError
from noteapp.domain.policies.attachment_policy import MAX_IMAGE_BYTES
from noteapp.infrastructure.attachment.file_reader import LocalImageFileReader

reader = LocalImageFileReader()


def test_reads_bytes_and_uses_only_the_leaf_as_name(tmp_path):
    path = tmp_path / "ảnh.png"
    path.write_bytes(b"abc")
    assert reader.read(str(path)) == (b"abc", "ảnh.png")


def test_oversized_file_is_rejected_by_stat(tmp_path):
    path = tmp_path / "big.bin"
    with open(path, "wb") as handle:
        handle.truncate(MAX_IMAGE_BYTES + 1)
    with pytest.raises(ImageTooLarge):
        reader.read(str(path))
    path.write_bytes(b"x" * MAX_IMAGE_BYTES)
    assert len(reader.read(str(path))[0]) == MAX_IMAGE_BYTES


@pytest.mark.parametrize("path", ["", None, 5])
def test_invalid_paths(path):
    with pytest.raises(ValidationError):
        reader.read(path)


def test_missing_path_and_directory_are_rejected(tmp_path):
    with pytest.raises(ValidationError):
        reader.read(str(tmp_path / "missing.png"))
    with pytest.raises(ValidationError):
        reader.read(str(tmp_path))


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="FIFOs need a POSIX platform")
def test_fifo_is_rejected_without_blocking(tmp_path):
    fifo = tmp_path / "pipe"
    os.mkfifo(fifo)
    with pytest.raises(ValidationError):
        reader.read(str(fifo))
