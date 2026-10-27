"""Split sections into retrieval-sized chunks without crossing section boundaries.

A chunk never mixes two sections, so every citation points at one page or heading.
Each chunk carries a context header ("Title > Section") that is searched and embedded
with it: a paragraph that says "Employees receive 30 days" is only findable as an
annual-leave rule if the heading travels with it.
"""

import re
from dataclasses import dataclass

from sovereign.ingestion.extract import Section

MAX_CHARS = 1200
OVERLAP_CHARS = 200


@dataclass
class Chunk:
    index: int
    context_header: str
    content: str
    location: dict

    @property
    def embedding_text(self) -> str:
        return f"{self.context_header}\n\n{self.content}"


def chunk_sections(title: str, sections: list[Section], max_chars: int = MAX_CHARS) -> list[Chunk]:
    chunks: list[Chunk] = []
    for section in sections:
        header = " > ".join([title, *section.location.get("path", [])])
        for piece in _split(section.text, max_chars):
            chunks.append(Chunk(len(chunks), header, piece, section.location))
    return chunks


def _split(text: str, max_chars: int) -> list[str]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    units: list[str] = []
    for paragraph in paragraphs:
        too_long = len(paragraph) > max_chars
        units.extend(_split_long(paragraph, max_chars) if too_long else [paragraph])

    pieces: list[str] = []
    current: list[str] = []
    size = 0
    for unit in units:
        if current and size + len(unit) > max_chars:
            pieces.append("\n\n".join(current))
            # Carry the last paragraph over when it's short, so a rule split across two
            # chunks is still readable in either.
            tail = current[-1]
            current, size = ([tail], len(tail)) if len(tail) <= OVERLAP_CHARS else ([], 0)
        current.append(unit)
        size += len(unit)
    if current:
        pieces.append("\n\n".join(current))
    return pieces


def _split_long(paragraph: str, max_chars: int) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", paragraph)
    pieces: list[str] = []
    current = ""
    for sentence in sentences:
        while len(sentence) > max_chars:  # no sentence breaks at all (tables, logs)
            pieces.append(sentence[:max_chars])
            sentence = sentence[max_chars:]
        if current and len(current) + len(sentence) + 1 > max_chars:
            pieces.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        pieces.append(current)
    return pieces
