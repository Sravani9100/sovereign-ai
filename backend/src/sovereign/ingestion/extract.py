"""Turn an uploaded file into sections of text, each with where it came from.

The file type is decided from the bytes, not the client's Content-Type or extension.
Scanned PDFs (no text layer) are rejected rather than indexed as empty.
"""

import io
import re
import zipfile
from dataclasses import dataclass, field

PDF = "application/pdf"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
MARKDOWN = "text/markdown"
TEXT = "text/plain"

# A DOCX is a zip; refuse archives that expand to something huge (zip bombs).
MAX_UNCOMPRESSED_BYTES = 100 * 1024 * 1024


class UnsupportedFile(ValueError):
    pass


class ExtractionError(ValueError):
    pass


@dataclass
class Section:
    text: str
    location: dict = field(default_factory=dict)  # {"page": 3} or {"section": "4.2 Leave"}


def detect_type(data: bytes, filename: str) -> str:
    if data.startswith(b"%PDF-"):
        return PDF
    if data.startswith(b"PK\x03\x04"):
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                if "word/document.xml" in archive.namelist():
                    return DOCX
        except zipfile.BadZipFile:
            pass
        raise UnsupportedFile("Only .docx archives are supported")
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        raise UnsupportedFile("Supported formats: PDF, DOCX, Markdown, plain text") from None
    if b"\x00" in data:
        raise UnsupportedFile("Binary files are not supported")
    return MARKDOWN if filename.lower().endswith((".md", ".markdown")) else TEXT


def extract(data: bytes, mime_type: str) -> list[Section]:
    match mime_type:
        case "application/pdf":
            sections = _pdf(data)
        case "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            sections = _docx(data)
        case "text/markdown":
            sections = _markdown(data.decode("utf-8"))
        case "text/plain":
            sections = [Section(data.decode("utf-8"))]
        case _:
            raise UnsupportedFile(mime_type)
    sections = [s for s in sections if s.text.strip()]
    if not sections:
        raise ExtractionError("No text found. Scanned documents need OCR, which isn't supported.")
    return sections


def _pdf(data: bytes) -> list[Section]:
    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(data))
        return [
            Section(page.extract_text() or "", {"page": number})
            for number, page in enumerate(reader.pages, start=1)
        ]
    except Exception as exc:  # pypdf raises many types for malformed files
        raise ExtractionError(f"Could not read PDF: {exc}") from exc


def _docx(data: bytes) -> list[Section]:
    import docx

    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        if sum(info.file_size for info in archive.infolist()) > MAX_UNCOMPRESSED_BYTES:
            raise ExtractionError("Document expands to more than 100 MB")
    document = docx.Document(io.BytesIO(data))

    sections: list[Section] = []
    headings: list[str] = []
    lines: list[str] = []

    def flush() -> None:
        if lines:
            sections.append(Section("\n".join(lines), _heading_location(headings)))
            lines.clear()

    for paragraph in document.paragraphs:
        style = paragraph.style.name if paragraph.style is not None else ""
        text = paragraph.text.strip()
        level = _heading_level(style)
        if level and text:
            flush()
            headings[level - 1 :] = [text]
        elif text:
            lines.append(text)
    flush()

    for table in document.tables:
        rows = [" | ".join(cell.text.strip() for cell in row.cells) for row in table.rows]
        sections.append(Section("\n".join(rows), {"section": "Table"}))
    return sections


def _heading_level(style: str) -> int:
    if style == "Title":
        return 1
    match = re.fullmatch(r"Heading (\d)", style)
    return int(match.group(1)) if match else 0


_MD_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")


def _markdown(text: str) -> list[Section]:
    sections: list[Section] = []
    headings: list[str] = []
    lines: list[str] = []
    in_code = False

    def flush() -> None:
        if any(line.strip() for line in lines):
            sections.append(Section("\n".join(lines).strip(), _heading_location(headings)))
        lines.clear()

    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            in_code = not in_code
        match = None if in_code else _MD_HEADING.match(line)
        if match:
            flush()
            # Replaces this level and everything below it. A skipped level (# then ###)
            # just appends, so the path stays [h1, h3].
            headings[len(match.group(1)) - 1 :] = [match.group(2)]
        else:
            lines.append(line)
    flush()
    return sections


def _heading_location(headings: list[str]) -> dict:
    if not headings:
        return {}
    return {"section": headings[-1], "path": list(headings)}
