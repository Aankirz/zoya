"""Reading aloud (Phase 5, STACK §8): documents with Amazon Textract, the screen with Rekognition.

- `read_document`: a PDF or image (the file open in the frontmost app when no path is given).
  Textract's synchronous AnalyzeDocument takes one page per call (PDF/TIFF 1 page, 10 MB), so PDF
  pages are rendered locally with Quartz and sent as JPEG, at most DOCUMENT_MAX_PAGES. TABLES
  gives rows and cells, read as "a | b | c".
- `read_screen_text`: Rekognition DetectText on the display under the frontmost window. It
  returns at most 100 words, so it is for short screens; describe_screen covers the rest.

Everything read is untrusted content (§12.2). Region ap-south-1, zoya-app IAM policy
(textract:AnalyzeDocument, rekognition:DetectText).

Docs: https://docs.aws.amazon.com/textract/latest/dg/limits-document.html
https://docs.aws.amazon.com/textract/latest/APIReference/API_AnalyzeDocument.html
https://docs.aws.amazon.com/textract/latest/dg/how-it-works-tables.html
https://developer.apple.com/documentation/coregraphics/cgpdfdocument
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from strands import tool

from zoya import safety, screen
from zoya.config import (
    DOCUMENT_MAX_PAGES,
    DOCUMENT_RENDER_DPI,
    DOCUMENT_TEXT_MAX_CHARS,
    TEXTRACT_TIMEOUT_S,
)
from zoya.tools import ToolError

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".tif", ".tiff"}
PDF_POINTS_PER_INCH = 72
TEXTRACT_MAX_BYTES = 10 * 1024 * 1024
MS_PER_S = 1000


# --- Textract blocks → speakable text (parser, tested) -------------------------------------------


def _child_ids(block: dict[str, Any]) -> list[str]:
    return [
        child
        for relation in block.get("Relationships", [])
        if relation.get("Type") == "CHILD"
        for child in relation.get("Ids", [])
    ]


def blocks_to_text(blocks: list[dict[str, Any]]) -> str:
    """LINE blocks in reading order, then each TABLE as rows of "cell | cell"."""
    by_id = {block.get("Id"): block for block in blocks}
    lines = [b["Text"] for b in blocks if b.get("BlockType") == "LINE" and b.get("Text")]
    tables = []
    for table in (b for b in blocks if b.get("BlockType") == "TABLE"):
        cells = [by_id[i] for i in _child_ids(table) if by_id.get(i, {}).get("BlockType") == "CELL"]
        rows: dict[int, dict[int, str]] = {}
        for cell in cells:
            words = [by_id[i].get("Text", "") for i in _child_ids(cell) if i in by_id]
            rows.setdefault(cell.get("RowIndex", 0), {})[cell.get("ColumnIndex", 0)] = " ".join(
                w for w in words if w
            )
        rendered = [" | ".join(row[c] for c in sorted(row)) for _r, row in sorted(rows.items())]
        tables.append(f"Table {len(tables) + 1}:\n" + "\n".join(rendered))
    return "\n".join(lines + tables)


# --- Files ---------------------------------------------------------------------------------------


def _front_document() -> Path:
    """The file shown in the frontmost window (AXDocument), e.g. a PDF open in Preview."""
    from zoya.screen import _ax
    from zoya.tools import ax

    _name, app = ax.front_app()
    window = _ax(app, "AXFocusedWindow")
    document = _ax(window, "AXDocument") if window is not None else None
    if not document:
        raise ToolError("I can't tell which document is open. Tell me the file, or open it first.")
    return Path(unquote(urlparse(str(document)).path))


def _pdf_pages(path: Path) -> list[bytes]:
    import Quartz

    raw = str(path).encode()
    url = Quartz.CFURLCreateFromFileSystemRepresentation(None, raw, len(raw), False)
    document = Quartz.CGPDFDocumentCreateWithURL(url)
    if document is None or not Quartz.CGPDFDocumentIsUnlocked(document):
        raise ToolError("I can't open that PDF. It may be password protected.")
    count = min(Quartz.CGPDFDocumentGetNumberOfPages(document), DOCUMENT_MAX_PAGES)
    return [_render_page(Quartz.CGPDFDocumentGetPage(document, n)) for n in range(1, count + 1)]


def _render_page(page: Any) -> bytes:
    import Quartz

    box = Quartz.CGPDFPageGetBoxRect(page, Quartz.kCGPDFMediaBox)
    scale = DOCUMENT_RENDER_DPI / PDF_POINTS_PER_INCH
    width, height = int(box.size.width * scale), int(box.size.height * scale)
    context = Quartz.CGBitmapContextCreate(
        None,
        width,
        height,
        8,
        width * 4,
        Quartz.CGColorSpaceCreateDeviceRGB(),
        Quartz.kCGImageAlphaPremultipliedLast,
    )
    Quartz.CGContextSetRGBFillColor(context, 1, 1, 1, 1)
    Quartz.CGContextFillRect(context, ((0, 0), (width, height)))
    Quartz.CGContextScaleCTM(context, scale, scale)
    Quartz.CGContextTranslateCTM(context, -box.origin.x, -box.origin.y)
    Quartz.CGContextDrawPDFPage(context, page)
    return screen._jpeg(Quartz.CGBitmapContextCreateImage(context))


def _pages(path: Path) -> list[bytes]:
    if not path.is_file():
        raise ToolError("I can't find that file.")
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _pdf_pages(path)
    if suffix not in IMAGE_SUFFIXES:
        raise ToolError("I can read PDFs and PNG, JPEG or TIFF images.")
    if path.stat().st_size > TEXTRACT_MAX_BYTES:
        raise ToolError("That image is too large for me to read.")
    return [path.read_bytes()]


@tool
def read_document(path: str = "") -> str:
    """Read a PDF, bill, letter or scanned image: its text and tables, to read aloud or answer
    questions about. Without a path it reads the document open in the frontmost app (e.g. Preview).

    Args:
        path: Optional full path of the file, e.g. "/Users/me/Downloads/bill.pdf".
    """
    started = time.monotonic()
    file = Path(path).expanduser() if path.strip() else _front_document()
    texts = []
    client = screen.aws_client("textract", TEXTRACT_TIMEOUT_S)
    for number, page in enumerate(_pages(file), start=1):
        try:
            response = client.analyze_document(Document={"Bytes": page}, FeatureTypes=["TABLES"])
        except Exception as error:  # noqa: BLE001 — AWS errors become a spoken reason
            raise ToolError("I couldn't read that document right now.") from error
        texts.append(f"Page {number}:\n{blocks_to_text(response.get('Blocks', []))}")
    screen_log(
        "read_document",
        pages=len(texts),
        textract_ms=round((time.monotonic() - started) * MS_PER_S),
    )
    body = "\n\n".join(texts)[:DOCUMENT_TEXT_MAX_CHARS]
    return f"Document {file.name}:\n" + safety.wrap_untrusted(body or "(no text found)")


@tool
def read_screen_text() -> str:
    """Read the words on the screen exactly (fast OCR, up to 100 words), top to bottom."""
    started = time.monotonic()
    shot = screen.capture_display()
    rows = safety.rows_from_ocr(screen.detect_text(shot.jpeg))
    screen_log("read_screen_text", ocr_ms=round((time.monotonic() - started) * MS_PER_S))
    return f"Frontmost app: {shot.app}\n" + safety.wrap_untrusted("\n".join(rows) or "(no text)")


def screen_log(stage: str, **fields: Any) -> None:
    from zoya.tools.computer import log_stage

    log_stage(stage, **fields)


TOOLS = [read_document, read_screen_text]
