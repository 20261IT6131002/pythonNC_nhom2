"""FR-15 artifact, privacy and write-failure contracts."""

from dataclasses import replace
from io import BytesIO
from pathlib import Path
from unittest.mock import Mock

import pytest
from PIL import Image
from pypdf import PdfReader

from noteapp.application.commands.export_note import (
    ExportFormat,
    ExportImage,
    ExportNote,
    ExportNoteInput,
    ExportSnapshot,
)
from noteapp.domain.errors import Conflict, ExportFailure, ExportLocked, NotFound, ValidationError
from noteapp.infrastructure.export.files import FileNoteExporter
from tests.repository_contracts import note

TITLE = "Ghi chú tiếng Việt"
BODY = "Điện thoại ở Nguyễn Trãi. Tiếng Việt có dấu. <img src='/etc/passwd'>"


@pytest.fixture
def image():
    data = BytesIO()
    Image.new("RGB", (60, 30), "blue").save(data, format="PNG")
    return ExportImage("image/png", data.getvalue())


def test_markdown_contains_exact_utf8_and_local_asset(tmp_path, image):
    snapshot = ExportSnapshot("../../đường dẫn", BODY, image)
    publisher = FileNoteExporter()
    first = Path(publisher.publish(snapshot, str(tmp_path), ExportFormat.MARKDOWN))
    second = Path(publisher.publish(snapshot, str(tmp_path), ExportFormat.MARKDOWN))
    assert first != second and first.parent.parent == second.parent.parent == tmp_path
    assert BODY in first.read_bytes().decode("utf-8")
    assert "![Ảnh đính kèm](assets/attachment.png)" in first.read_text(encoding="utf-8")
    assert (first.parent / "assets" / "attachment.png").read_bytes() == image.data


def test_pdf_embeds_vietnamese_font_wraps_and_includes_image(tmp_path, image):
    snapshot = ExportSnapshot(TITLE, "\n".join([BODY] * 60), image)
    output = FileNoteExporter().publish(snapshot, str(tmp_path), ExportFormat.PDF)
    reader = PdfReader(output)
    assert len(reader.pages) > 1
    text = "\n".join(page.extract_text() for page in reader.pages)
    assert TITLE in text and BODY in text
    assert any(page.images for page in reader.pages)
    fonts = reader.pages[0]["/Resources"]["/Font"]
    assert any("/ToUnicode" in ref.get_object() for ref in fonts.values())


def test_export_write_failure_cleans_staging_and_leaves_existing_files(tmp_path, monkeypatch):
    existing = tmp_path / "existing.md"
    existing.write_text("keep me", encoding="utf-8")

    def refuse_write(*args, **kwargs):
        raise PermissionError("internal filesystem details")

    monkeypatch.setattr(Path, "rename", refuse_write)
    with pytest.raises(ExportFailure, match="selected directory") as error:
        FileNoteExporter().publish(
            ExportSnapshot(TITLE, BODY), str(tmp_path), ExportFormat.MARKDOWN
        )
    assert error.value.__cause__ is None
    assert list(tmp_path.iterdir()) == [existing]
    assert existing.read_text(encoding="utf-8") == "keep me"
    with pytest.raises(ValidationError):
        FileNoteExporter().publish(ExportSnapshot(TITLE, BODY), "../escape", ExportFormat.MARKDOWN)


def test_export_reads_current_server_record_before_publishing(tmp_path):
    repository, attachments, publisher = Mock(), Mock(), Mock()
    service = ExportNote(repository, attachments, publisher)
    saved = note()
    command = ExportNoteInput(saved.id, saved.version, str(tmp_path), ExportFormat.PDF)
    repository.find_by_id.return_value = None
    with pytest.raises(NotFound):
        service.execute(command)
    repository.find_by_id.return_value = replace(saved, version=saved.version + 1)
    with pytest.raises(Conflict):
        service.execute(command)
    repository.find_by_id.return_value = Mock(is_locked=True)
    with pytest.raises(ExportLocked):
        service.execute(command)
    publisher.publish.assert_not_called()
    attachments.get.assert_not_called()

    repository.find_by_id.return_value = saved
    publisher.publish.return_value = "published"
    assert service.execute(command) == "published"
    publisher.publish.assert_called_once_with(
        ExportSnapshot(saved.title, saved.content), str(tmp_path), ExportFormat.PDF
    )
