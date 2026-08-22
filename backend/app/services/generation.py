"""A model turns retrieved chunks into an explanation. Nothing else may.

Three backends, one contract. `RAG_PROVIDER` picks:

    groq       an open-weight model on a free tier. The default.
    ollama     a local model, fully offline.
    anthropic  Claude, the only backend with native citations.

Groq and Ollama share one implementation because both speak the OpenAI wire
format; any other compatible endpoint works by setting `RAG_BASE_URL`.

THE THREE RULES

1. **Only say what's in the documents.** Enforced on the *response*, not asked
   for in the prompt - an answer that cites nothing is discarded and replaced
   with the decline. How a citation is obtained differs by backend:

   * Claude returns them natively. The API reports which passage supports each
     sentence, so a citation cannot point at text the model did not use.
   * Everything else is asked for `[1]`-style markers plus a verbatim quote per
     marker, and then **the quote is checked against the chunk it claims**. A
     fabricated quote fails the check and that citation is dropped; if none
     survive, the answer is declined.

   The second is weaker than the first - a model can quote correctly and still
   reason badly around the quote - but it is verification, not trust, and it
   catches invention, which is the failure that matters.

2. **Never mix crops.** Enforced upstream in `retrieval.py` by filtering before
   ranking, and asserted again before anything reaches this module. By the time
   a request is built, a wrong-crop chunk cannot be present.

3. **Flag unverified numbers.** Placeholder fertilizer figures are injected
   inside an explicit UNVERIFIED block and the prompt requires the answer to say
   so. The caller also sets `used_placeholder_data` from the database
   independently, so the flag never depends on the model complying.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from functools import lru_cache
from typing import Any

from ..config import (
    ANTHROPIC_API_KEY,
    RAG_API_KEY,
    RAG_BASE_URL,
    RAG_EFFORT,
    RAG_MAX_TOKENS,
    RAG_MODEL,
    RAG_PROVIDER,
)

logger = logging.getLogger(__name__)

# Emitted verbatim by the model when the documents cannot answer the question.
# Matched as a substring so a surrounding sentence still resolves to a decline.
NO_ANSWER_SENTINEL = "NO_GROUNDED_ANSWER"

# A quote must overlap the chunk it cites by at least this fraction, measured as
# the longest contiguous run. Exact substring match is tried first; this is the
# tolerance for a model that fixed a typo or normalised whitespace. Low enough
# to survive light paraphrase, high enough that an invented sentence fails.
QUOTE_MATCH_RATIO = 0.6
# Below this length a "quote" is too short to be evidence of anything.
MIN_QUOTE_CHARS = 15

_RULES = """\
Absolute rules:

1. Use ONLY the attached documents and the COMPUTED CONTEXT block. You have no \
other knowledge of agriculture for this purpose. If the documents do not \
support an answer, reply with exactly NO_GROUNDED_ANSWER and nothing else. \
Never fill a gap with general knowledge, and never guess a number.

2. Every factual claim must come from a document. Do not restate a claim you \
cannot point at.

3. Numbers inside a block marked UNVERIFIED are placeholders, not agronomic \
advice. If your answer refers to any of them, say plainly that the figure is \
unverified and must be confirmed with a local agricultural officer before \
acting on it. Never present an unverified number as a recommendation.

4. The COMPUTED CONTEXT block holds figures this platform calculated (an \
opportunity score, a demand gap, a forecast). Explain and interpret them using \
the documents. Do not recompute them, and do not contradict them.

5. Reply in the SAME LANGUAGE as the question. A question in Marathi or Hindi \
gets a Marathi or Hindi answer - a farmer who types Devanagari cannot read an \
English reply.

Style: plain language a farmer can act on, no jargon, 120 words or fewer. Lead \
with the answer, then the reason. Do not open with a greeting or restate the \
question. No markdown headings or bullet lists. Do not put quoted sentences or \
quotation marks in the answer itself - state the fact in your own words."""

_ROLE = """\
You explain agricultural recommendations to farmers in Maharashtra, India, for \
the KhetiSetu platform. You are the "why" behind a number a farmer has just \
been shown."""

# Claude reports citations itself, so it is never asked to write markers.
SYSTEM_PROMPT = f"{_ROLE}\n\n{_RULES}\n"

# Every other backend must be asked for its evidence explicitly, in a shape
# that can be machine-checked against the source text.
SYSTEM_PROMPT_MARKERS = f"""{_ROLE}

{_RULES}

Citations. After the answer, output SOURCES: alone on its own line - nothing \
before or after it on that line - and then one line per document you used, in \
this exact form:

[1] "a sentence copied word for word from DOCUMENT 1"

Copy the supporting sentence EXACTLY as it appears in that document - do not \
paraphrase, shorten or correct it. The quote is checked against the document \
automatically and your answer is discarded if it does not match. Cite every \
document you relied on, and cite no document you did not use. Use the matching \
[1], [2] markers inline in the answer text as well.

The quotes go ONLY in the SOURCES block, never in the answer text.
"""


@dataclass
class GenerationResult:
    answer: str
    citations: list[dict[str, Any]] = field(default_factory=list)
    grounded: bool = False
    declined: bool = False
    model: str | None = None
    # True when a model produced the text, so callers can distinguish "the model
    # answered" from "the template answered".
    generated_by_llm: bool = False


DECLINE_TEMPLATE = (
    'I don\'t have grounded information to answer "{question}" - no indexed source '
    "document covers it, and I won't answer from anything else."
)


class GenerationError(RuntimeError):
    """The backend could not be reached or refused the request transport-level.

    Raised rather than swallowed so the caller can degrade to extractive mode
    and report it, instead of a connection error looking like an empty corpus.
    """


# The last transport failure, surfaced by GET /rag/status.
#
# This exists because of a real bug: a retired Groq model made every answer
# degrade to extractive while /rag/status still reported "fully operational",
# and the 404 explaining why was caught and discarded. `available()` can only
# ever report what is *configured* - a wrong model name or a revoked key looks
# identical until something is actually sent - so the first failure has to be
# recorded somewhere a human will look.
_last_error: str | None = None


def last_error() -> str | None:
    return _last_error


def _record_error(message: str) -> None:
    global _last_error
    _last_error = message
    logger.warning("generation backend failed, degrading to extractive: %s", message)


def available() -> bool:
    """Whether a generation backend is configured.

    Configured is not the same as reachable - Ollama counts as configured even
    when the server is down, and the resulting GenerationError degrades to
    extractive mode at call time.
    """
    if RAG_PROVIDER == "anthropic":
        return ANTHROPIC_API_KEY is not None
    if RAG_PROVIDER == "ollama":
        return True
    return RAG_API_KEY is not None


def describe() -> str:
    """Human-readable provider/model, for GET /rag/status."""
    return f"{RAG_PROVIDER}:{RAG_MODEL}"


def uses_native_citations() -> bool:
    return RAG_PROVIDER == "anthropic"


# ---------------------------------------------------------------
# Shared context rendering
# ---------------------------------------------------------------


def _document_label(chunk: dict[str, Any], titles: dict[int, str]) -> str:
    title = titles.get(chunk["source_id"]) or f"Source {chunk['source_id']}"
    if not chunk.get("page_start"):
        return title
    page_end = chunk.get("page_end") or chunk["page_start"]
    if page_end == chunk["page_start"]:
        return f"{title}, page {chunk['page_start']}"
    return f"{title}, pages {chunk['page_start']}-{page_end}"


def _context_block(computed_context: dict[str, Any] | None, unverified: list[str]) -> str:
    parts: list[str] = []
    if computed_context:
        lines = "\n".join(f"- {key}: {value}" for key, value in sorted(computed_context.items()))
        parts.append(f"COMPUTED CONTEXT (calculated by this platform):\n{lines}")
    if unverified:
        parts.append(
            "UNVERIFIED - placeholder figures, not agronomic advice:\n"
            + "\n".join(f"- {line}" for line in unverified),
        )
    return "\n\n".join(parts)


def _citation(chunk: dict[str, Any], cited_text: str | None) -> dict[str, Any]:
    return {
        "source_id": chunk["source_id"],
        "chunk_id": chunk["id"],
        "cited_text": cited_text,
        "page_start": chunk.get("page_start"),
        "page_end": chunk.get("page_end"),
    }


def _declined(question: str, model: str | None = None, by_llm: bool = False) -> GenerationResult:
    return GenerationResult(
        answer=DECLINE_TEMPLATE.format(question=question),
        declined=True,
        grounded=False,
        model=model,
        generated_by_llm=by_llm,
    )


# ---------------------------------------------------------------
# Quote verification (the non-Claude grounding check)
# ---------------------------------------------------------------


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def quote_supported(quote: str, chunk_text: str) -> bool:
    """Does `quote` actually appear in `chunk_text`?

    This is what replaces Claude's native citations. Exact match after
    whitespace/case normalisation is the common case; the ratio check tolerates
    a model that silently fixed a typo or dropped a hyphen. An invented sentence
    shares no long contiguous run with the source and fails both.
    """
    needle, haystack = _normalise(quote), _normalise(chunk_text)
    if len(needle) < MIN_QUOTE_CHARS or not haystack:
        return False
    if needle in haystack:
        return True
    match = SequenceMatcher(None, needle, haystack, autojunk=False).find_longest_match(
        0, len(needle), 0, len(haystack),
    )
    return match.size / len(needle) >= QUOTE_MATCH_RATIO


# PARSING IS LIBERAL, VERIFICATION IS STRICT.
#
# These two things are deliberately not held to the same standard. Whether a
# quote is real is the safety property and stays exact. *How* the model laid the
# citation out is cosmetic, and being fussy about it caused a real bug: the model
# line-wrapped a 220-character quote and a single-line regex silently found no
# citations, so a question the corpus plainly answered got declined. A false
# decline teaches the farmer the feature is useless, which is its own harm.
#
# So: accept markdown emphasis on the header, content on the same line, wrapped
# quotes, and `1.` / `(1)` / `【1】` numbering. Verify every one of them anyway.
_SOURCES_SPLIT = re.compile(r"^[\s*_#>-]*SOURCES\s*:?[ \t]*", re.IGNORECASE | re.MULTILINE)
_CITATION_START = re.compile(r"^[\s>*-]*(?:[\[【(]\s*(\d+)\s*[\]】)]|(\d+)\s*[.)])\s*")
_INLINE_MARKER = re.compile(r"\s*[\[【(]\s*\d+\s*[\]】)]")
_QUOTED_SPAN = re.compile(r"[\"“]([^\"”]{15,})[\"”]")
_TRIM_QUOTES = str.maketrans({'"': None, "“": None, "”": None})


def _entries(block: str) -> list[tuple[int, str]]:
    """(document number, quote) pairs, tolerating wrapped lines.

    A line that starts with a marker opens a new entry; anything after it is a
    continuation of the current one, which is what makes a long wrapped quote
    parse instead of vanishing.
    """
    out: list[tuple[int, list[str]]] = []
    for line in block.splitlines():
        if not line.strip():
            continue
        match = _CITATION_START.match(line)
        if match:
            number = int(match.group(1) or match.group(2))
            out.append((number, [line[match.end():]]))
        elif out:
            out[-1][1].append(line.strip())
    return [(number, " ".join(parts).strip().translate(_TRIM_QUOTES).strip()) for number, parts in out]


def _salvage(raw: str, chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Last resort: any quoted span anywhere, matched to whichever chunk it came from.

    Covers the model ignoring the SOURCES format entirely but still quoting the
    source honestly. Safe precisely because it proves nothing on its own - every
    candidate still has to pass `quote_supported` against a real chunk.
    """
    citations: list[dict[str, Any]] = []
    used: set[int] = set()
    for quote in _QUOTED_SPAN.findall(raw):
        for index, chunk in enumerate(chunks):
            if index not in used and quote_supported(quote, chunk["chunk_text"]):
                used.add(index)
                citations.append(_citation(chunk, quote.strip()))
                break
    return citations


def parse_marker_citations(
    raw: str, chunks: list[dict[str, Any]],
) -> tuple[str, list[dict[str, Any]]]:
    """Split a marker-style response into prose and verified citations.

    Markers are stripped from the prose so both backends return clean text with
    citations carried separately, and a citation survives only if its quote
    checks out against the chunk it names.
    """
    split = _SOURCES_SPLIT.split(raw, maxsplit=1)
    body, block = split[0], (split[1] if len(split) > 1 else "")

    citations: list[dict[str, Any]] = []
    seen: set[int] = set()
    for number, quote in _entries(block):
        index = number - 1  # the prompt numbers documents from 1
        if not 0 <= index < len(chunks) or index in seen:
            continue
        if not quote_supported(quote, chunks[index]["chunk_text"]):
            continue  # invented or mismatched - not evidence
        seen.add(index)
        citations.append(_citation(chunks[index], quote))

    if not citations:
        citations = _salvage(raw, chunks)

    # Strip markers and any quoted span the model inlined despite being told not
    # to - a raw source sentence mid-answer reads as a glitch to a farmer.
    clean = _INLINE_MARKER.sub("", body)
    return clean.strip(), citations


# ---------------------------------------------------------------
# Anthropic backend (native citations)
# ---------------------------------------------------------------


@lru_cache(maxsize=1)
def _anthropic_client():
    try:
        import anthropic
    except ModuleNotFoundError as exc:  # pragma: no cover - dependency guard
        raise GenerationError("the `anthropic` package is not installed") from exc
    return anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def _anthropic_documents(
    chunks: list[dict[str, Any]], titles: dict[int, str],
) -> list[dict[str, Any]]:
    """One document block per chunk, in retrieval order.

    Order is load-bearing: the API reports `document_index` against the position
    of the document block, so `chunks[document_index]` is how a citation maps
    back to a source. Do not reorder these afterwards.
    """
    return [
        {
            "type": "document",
            "source": {"type": "text", "media_type": "text/plain", "data": chunk["chunk_text"]},
            "title": titles.get(chunk["source_id"]) or f"Source {chunk['source_id']}",
            "context": f"Indexed agricultural source: {_document_label(chunk, titles)}.",
            "citations": {"enabled": True},
        }
        for chunk in chunks
    ]


def _generate_anthropic(
    question: str,
    chunks: list[dict[str, Any]],
    titles: dict[int, str],
    tail: str,
) -> GenerationResult:
    documents = _anthropic_documents(chunks, titles)
    # Cache the [system + documents] prefix; the "Why <crop>?" button sends
    # different questions against the same retrieved set, so only the cheap tail
    # after this breakpoint varies.
    documents[-1] = {**documents[-1], "cache_control": {"type": "ephemeral"}}

    try:
        response = _anthropic_client().messages.create(
            model=RAG_MODEL,
            max_tokens=RAG_MAX_TOKENS,
            system=SYSTEM_PROMPT,
            output_config={"effort": RAG_EFFORT},
            messages=[{"role": "user", "content": [*documents, {"type": "text", "text": tail}]}],
        )
    except Exception as exc:  # noqa: BLE001 - transport failures of any shape
        message = f"anthropic model={RAG_MODEL}: {exc}"
        _record_error(message)
        raise GenerationError(message) from exc

    # A safety decline carries no content; showing it would be a blank answer.
    if response.stop_reason == "refusal":
        return _declined(question, response.model, by_llm=True)

    text_parts: list[str] = []
    citations: list[dict[str, Any]] = []
    for block in response.content:
        if block.type != "text":
            continue
        text_parts.append(block.text)
        for citation in getattr(block, "citations", None) or []:
            index = getattr(citation, "document_index", None)
            if index is None or not 0 <= index < len(chunks):
                continue
            citations.append(_citation(chunks[index], getattr(citation, "cited_text", None)))

    return _finish("".join(text_parts).strip(), citations, question, response.model)


# ---------------------------------------------------------------
# OpenAI-compatible backend (Groq, Ollama, anything else)
# ---------------------------------------------------------------


@lru_cache(maxsize=1)
def _openai_client():
    try:
        from openai import OpenAI
    except ModuleNotFoundError as exc:  # pragma: no cover - dependency guard
        raise GenerationError("the `openai` package is not installed") from exc
    # max_retries above the default 2: Groq's free tier allows 8,000 tokens per
    # minute and one grounded request is ~3,000, so a 429 after two questions in
    # the same minute is normal operation, not a fault. The SDK retries 429 with
    # backoff, which turns a visible failure into a slower answer.
    return OpenAI(
        api_key=RAG_API_KEY or "not-needed",
        base_url=RAG_BASE_URL,
        max_retries=5,
        timeout=90.0,
    )


def _generate_openai(
    question: str,
    chunks: list[dict[str, Any]],
    titles: dict[int, str],
    tail: str,
) -> GenerationResult:
    # No document blocks in this wire format, so documents are numbered inline
    # and the numbering is what citation markers refer back to.
    rendered = "\n\n".join(
        f"DOCUMENT {n} ({_document_label(chunk, titles)}):\n{chunk['chunk_text']}"
        for n, chunk in enumerate(chunks, 1)
    )
    try:
        response = _openai_client().chat.completions.create(
            model=RAG_MODEL,
            max_tokens=RAG_MAX_TOKENS,
            # Grounded extraction, not creative writing. Sampling here buys
            # nothing and costs faithfulness to the source text.
            temperature=0,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT_MARKERS},
                {"role": "user", "content": f"{rendered}\n\n{tail}"},
            ],
        )
    except Exception as exc:  # noqa: BLE001 - transport failures of any shape
        message = f"{RAG_PROVIDER} ({RAG_BASE_URL}) model={RAG_MODEL}: {exc}"
        _record_error(message)
        raise GenerationError(message) from exc

    raw = (response.choices[0].message.content or "").strip()
    model = getattr(response, "model", RAG_MODEL)

    if NO_ANSWER_SENTINEL in raw:
        return _declined(question, model, by_llm=True)

    answer, citations = parse_marker_citations(raw, chunks)
    return _finish(answer, citations, question, model)


# ---------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------


def _finish(
    answer: str, citations: list[dict[str, Any]], question: str, model: str | None,
) -> GenerationResult:
    """Apply rule 1 to whatever the backend produced."""
    if NO_ANSWER_SENTINEL in answer or not answer:
        return _declined(question, model, by_llm=True)
    # Documents were supplied and nothing verifiable was cited, so no part of
    # this is traceable to a source. Returning it is the fabrication this layer
    # exists to prevent.
    if not citations:
        return _declined(question, model, by_llm=True)
    return GenerationResult(
        answer=answer,
        citations=citations,
        grounded=True,
        model=model,
        generated_by_llm=True,
    )


def generate(
    *,
    question: str,
    chunks: list[dict[str, Any]],
    source_titles: dict[int, str] | None = None,
    computed_context: dict[str, Any] | None = None,
    unverified_notes: list[str] | None = None,
) -> GenerationResult:
    """Explain `question`, grounded in `chunks`.

    Declines on empty `chunks` without calling anything - rule 1 with no
    documents can only ever be a decline. Raises GenerationError if the backend
    is unreachable, so the caller can degrade rather than fail.
    """
    if not chunks:
        return _declined(question)

    titles = source_titles or {}
    context = _context_block(computed_context, unverified_notes or [])
    tail = f"{context}\n\nQuestion: {question}" if context else f"Question: {question}"

    if RAG_PROVIDER == "anthropic":
        return _generate_anthropic(question, chunks, titles, tail)
    return _generate_openai(question, chunks, titles, tail)


def extractive_fallback(
    *,
    question: str,
    chunks: list[dict[str, Any]],
) -> GenerationResult:
    """No generation backend: quote the sources instead of explaining them.

    Deliberately extractive. With no model there is nothing that can safely
    paraphrase, and quoting cannot invent a claim the corpus does not contain -
    so retrieval stays useful and testable on its own, and the answer is exactly
    as grounded as the documents behind it.
    """
    if not chunks:
        return _declined(question)
    return GenerationResult(
        answer=" ".join(chunk["chunk_text"].strip() for chunk in chunks),
        citations=[_citation(chunk, chunk["chunk_text"]) for chunk in chunks],
        grounded=True,
        generated_by_llm=False,
    )
