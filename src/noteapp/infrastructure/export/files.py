"""Portable UTF-8 Markdown bundles and Unicode PDFs."""

import re
from gzip import decompress
from importlib.resources import files
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Lock
from unicodedata import normalize
from uuid import uuid4
from xml.sax.saxutils import escape

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer

from noteapp.application.commands.export_note import ExportFormat, ExportSnapshot
from noteapp.domain.errors import ExportFailure, ValidationError

FONT_NAME = "NoteApp-DejaVuSans"
FONT_LOCK = Lock()
EXTENSIONS = {"image/png": "png", "image/jpeg": "jpg", "image/gif": "gif", "image/webp": "webp"}


def _markdown(snapshot: ExportSnapshot, directory: Path) -> str:
    title = re.sub(r"([\\`*_{}\[\]()#+.!|<>-])", r"\\\1", snapshot.title)
    document = f"# {title}\n\n{snapshot.content}"
    if snapshot.image is not None:
        suffix = EXTENSIONS.get(snapshot.image.mime_type)
        if suffix is None:
            raise ExportFailure("Stored image type is unsupported.")
        filename = f"attachment.{suffix}"
        assets = directory / "assets"
        assets.mkdir()
        (assets / filename).write_bytes(snapshot.image.data)
        document += f"\n\n![Ảnh đính kèm](assets/{filename})"
    filename = "note.md"
    (directory / filename).write_text(document + "\n", encoding="utf-8", newline="\n")
    return filename


def _pdf(snapshot: ExportSnapshot, target: Path) -> None:
    # ReportLab font registration and subset generation use process-global state.
    with FONT_LOCK:
        if FONT_NAME not in pdfmetrics.getRegisteredFontNames():
            font = files("noteapp").joinpath("infrastructure/export/fonts/DejaVuSans.ttf.gz")
            pdfmetrics.registerFont(TTFont(FONT_NAME, BytesIO(decompress(font.read_bytes()))))
        title_style = ParagraphStyle("note_title", fontName=FONT_NAME, fontSize=19, leading=25)
        body_style = ParagraphStyle("note_body", fontName=FONT_NAME, fontSize=11, leading=17)
        doc = SimpleDocTemplate(str(target), pagesize=A4)
        story = [Paragraph(_literal(snapshot.title), title_style), Spacer(1, 14)]
        # Give each input line its own flowable so long notes can paginate.
        for line in snapshot.content.split("\n"):
            story.append(Paragraph(_literal(line), body_style) if line.strip() else Spacer(1, 17))
        if snapshot.image is not None:
            image = Image(BytesIO(snapshot.image.data))
            scale = min(1, (doc.width - 12) / image.drawWidth, (doc.height - 24) / image.drawHeight)
            image.drawWidth *= scale
            image.drawHeight *= scale
            story.extend([Spacer(1, 12), image])
        doc.build(story)


def _literal(text: str) -> str:
    clean = "".join(c if c == "\t" or ord(c) >= 32 else " " for c in normalize("NFC", text))
    return escape(clean.expandtabs(4)).replace("  ", "&nbsp; ")


class FileNoteExporter:
    def publish(self, snapshot: ExportSnapshot, directory: str, format: ExportFormat) -> str:
        if not isinstance(directory, str) or not directory or "\x00" in directory:
            raise ValidationError("Choose an export directory.")
        parent = Path(directory)
        if not parent.is_absolute():
            raise ValidationError("Choose an absolute export directory.")
        # Never derive paths from note titles or uploaded names. Publish a complete
        # directory in one rename on the chosen filesystem.
        try:
            parent = parent.resolve(strict=True)
            with TemporaryDirectory(prefix=".noteapp-export-", dir=parent) as temporary:
                staging = Path(temporary) / "bundle"
                staging.mkdir(mode=0o700)
                if format is ExportFormat.MARKDOWN:
                    filename = _markdown(snapshot, staging)
                else:
                    filename = "note.pdf"
                    _pdf(snapshot, staging / filename)
                destination = parent / f"note-{uuid4().hex}"
                if destination.exists():
                    raise ExportFailure("The export destination already exists.")
                staging.rename(destination)
                return str(destination / filename)
        except (OSError, ValueError):
            raise ExportFailure("Export could not be written to the selected directory.") from None
