"""Split a document into retrievable chunks.

Chunking is the part of a RAG system that quietly decides how good it can
possibly be, so the choices here are deliberate:

* **Paragraph boundaries first.** Agricultural bulletins are written in short
  topical paragraphs ("Nutrient management", "Sowing window"). Cutting at a
  fixed character count mid-sentence produces chunks whose embedding averages
  two unrelated topics, which is how a retriever starts returning things that
  are nearly relevant. Paragraphs are packed whole until the target size.

* **Sentence-level overlap.** A dose that reads "...apply 40 kg/ha. This is
  split across two applications." loses its meaning if the split falls between
  those sentences. Each chunk therefore repeats the tail of the previous one, so
  a fact that straddles a boundary is complete in at least one chunk.

* **Character targets, not token counts.** Sizing does not need token
  precision, and calling a tokenizer API per chunk would cost a round trip per
  paragraph to change nothing. `token_count` is recorded as an estimate and
  labelled as one.

* **Offsets are preserved.** `char_start`/`char_end` are positions in the
  original document and `page_start`/`page_end` come from the page the offset
  falls in, so a citation resolves to a place a human can open and check.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

# ~1,200 characters is roughly 250-300 tokens: one topic, small enough that a
# single embedding still represents it, large enough to carry a full
# recommendation with its qualifiers.
TARGET_CHARS = 1200
# A paragraph longer than this is split internally rather than shipped whole.
MAX_CHARS = 2000
# Repeated tail. Enough for a sentence or two of context.
OVERLAP_CHARS = 200
# Below this a chunk is noise - a stray heading, a page number, a caption.
MIN_CHARS = 80

# Characters per token, for the recorded estimate only. English prose sits near
# 4; agricultural text with many numbers and units runs a little denser.
CHARS_PER_TOKEN = 3.8

_PARAGRAPH = re.compile(r"\n\s*\n+")
_SENTENCE = re.compile(r"(?<=[.!?])\s+")
_WHITESPACE = re.compile(r"[ \t]+")


@dataclass
class Page:
    number: int
    text: str


@dataclass
class Chunk:
    index: int
    text: str
    char_start: int
    char_end: int
    page_start: int | None
    page_end: int | None
    token_estimate: int
    sha256: str


def normalise(text: str) -> str:
    """Collapse the artefacts of PDF text extraction.

    Hyphenated line breaks ("nitro-\ngen") and single newlines inside a
    paragraph are extraction noise, not authorial intent; blank lines are real
    paragraph breaks and are kept.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"-\n(\w)", r"\1", text)                  # de-hyphenate
    text = re.sub(r"(?<!\n)\n(?!\n)", " ", text)            # unwrap soft breaks
    text = _WHITESPACE.sub(" ", text)
    return text.strip()


def _split_long(paragraph: str) -> list[str]:
    """Break an over-long paragraph on sentence boundaries."""
    sentences = _SENTENCE.split(paragraph)
    out: list[str] = []
    current = ""
    for sentence in sentences:
        if current and len(current) + len(sentence) + 1 > TARGET_CHARS:
            out.append(current.strip())
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current.strip():
        out.append(current.strip())
    return out


def _tail(text: str, budget: int) -> str:
    """The last whole sentence(s) of `text`, up to `budget` characters."""
    if len(text) <= budget:
        return text
    window = text[-budget:]
    sentences = _SENTENCE.split(window)
    return " ".join(sentences[1:]).strip() if len(sentences) > 1 else window.strip()


def _page_span(pages: list[tuple[int, int, int]], start: int, end: int) -> tuple[int | None, int | None]:
    """Which pages the [start, end) character range touches."""
    touched = [number for number, p_start, p_end in pages if p_start < end and p_end > start]
    return (min(touched), max(touched)) if touched else (None, None)


def chunk_pages(pages: list[Page]) -> list[Chunk]:
    """Chunk a document supplied as pages.

    Pages are joined into one continuous document before splitting, so a
    paragraph that runs across a page break stays one paragraph instead of
    becoming two half-chunks.
    """
    document = ""
    spans: list[tuple[int, int, int]] = []
    for page in pages:
        cleaned = normalise(page.text)
        if not cleaned:
            continue
        start = len(document)
        document += cleaned + "\n\n"
        spans.append((page.number, start, len(document)))

    if not document.strip():
        return []

    # Pack paragraphs up to the target, splitting any that are too big alone.
    units: list[str] = []
    for paragraph in _PARAGRAPH.split(document):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        units.extend(_split_long(paragraph) if len(paragraph) > MAX_CHARS else [paragraph])

    packed: list[str] = []
    current = ""
    for unit in units:
        if current and len(current) + len(unit) + 2 > TARGET_CHARS:
            packed.append(current)
            current = unit
        else:
            current = f"{current}\n\n{unit}" if current else unit
    if current:
        packed.append(current)

    chunks: list[Chunk] = []
    search_from = 0
    for body in packed:
        # Locate the chunk in the original document to get true offsets. The
        # first fragment is unique enough to anchor on, and searching forward
        # only means a repeated heading cannot rewind the cursor.
        anchor = body[:60]
        found = document.find(anchor, search_from)
        char_start = found if found != -1 else search_from
        char_end = char_start + len(body)
        search_from = max(char_start + 1, char_end - OVERLAP_CHARS)

        text = body
        if chunks:
            carry = _tail(chunks[-1].text, OVERLAP_CHARS)
            if carry:
                text = f"{carry} {body}"
                char_start = max(0, char_start - len(carry) - 1)

        if len(text) < MIN_CHARS:
            continue

        page_start, page_end = _page_span(spans, char_start, char_end)
        chunks.append(
            Chunk(
                index=len(chunks),
                text=text,
                char_start=char_start,
                char_end=char_end,
                page_start=page_start,
                page_end=page_end,
                token_estimate=round(len(text) / CHARS_PER_TOKEN),
                sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
            ),
        )
    return chunks


def chunk_text(text: str) -> list[Chunk]:
    """Chunk a document with no page structure (.txt, .md)."""
    return chunk_pages([Page(number=1, text=text)])
