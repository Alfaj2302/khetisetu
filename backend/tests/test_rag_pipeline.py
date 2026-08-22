"""The RAG layer: chunking, crop resolution, retrieval, generation, guardrails.

No network. The Claude path is exercised against a fake client so the rules
that matter - decline when nothing is cited, decline on the sentinel, map
citations back to the right source - are actually tested rather than assumed
to work once a key is present.

The three guardrails from the spec each have tests that fail loudly if the
enforcement is removed:

    only say what's in the documents  ->  test_generate_declines_when_*
    never mix crops                   ->  test_*crop_isolation*
    flag unverified numbers           ->  test_*placeholder*/*unverified*
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.config import EMBEDDING_DIM, EMBEDDING_MODEL
from app.services import crop_lexicon, embeddings, generation, rag, retrieval
from rag.chunk import Page, chunk_pages, chunk_text, normalise

API = "/api/v1"


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------


def test_normalise_repairs_pdf_extraction_artefacts():
    raw = "Apply nitro-\ngen at sowing.\nSplit the dose.\n\nNext topic."
    out = normalise(raw)
    assert "nitrogen at sowing" in out       # de-hyphenated across the line break
    assert "sowing. Split" in out            # soft newline unwrapped to a space
    assert "\n\n" in out                     # real paragraph break survives


def test_chunking_packs_whole_paragraphs_and_respects_the_target():
    paragraphs = [f"Paragraph {i} about nutrient management. " * 8 for i in range(10)]
    chunks = chunk_text("\n\n".join(paragraphs))

    assert len(chunks) > 1
    # Overlap is prepended, so a chunk can exceed TARGET; the packed body cannot
    # run away entirely.
    assert all(len(c.text) < 2600 for c in chunks)
    assert [c.index for c in chunks] == list(range(len(chunks)))
    assert all(c.sha256 and len(c.sha256) == 64 for c in chunks)


def test_chunk_overlap_keeps_a_straddling_fact_whole():
    """A dose and its qualifier must survive landing on a chunk boundary."""
    filler = "General guidance on land preparation and weeding. " * 30
    chunks = chunk_text(f"{filler}\n\nApply 40 kg per hectare of nitrogen. "
                        f"This is split across two applications.\n\n{filler}")
    joined = [c.text for c in chunks]
    assert any("40 kg per hectare" in t for t in joined)
    # Some chunk repeats a tail of its predecessor.
    assert any(
        chunks[i].text[:60].strip() and chunks[i].text[:60] in chunks[i - 1].text
        for i in range(1, len(chunks))
    )


def test_chunks_carry_the_page_they_came_from():
    pages = [Page(number=n, text=f"Page {n} content about crop nutrition. " * 25) for n in (1, 2, 3)]
    chunks = chunk_pages(pages)
    assert chunks
    assert all(c.page_start is not None for c in chunks)
    assert min(c.page_start for c in chunks) == 1
    assert max(c.page_end for c in chunks) == 3
    assert all(c.char_start < c.char_end for c in chunks)


def test_chunking_drops_scraps_and_handles_empty_input():
    assert chunk_text("") == []
    assert chunk_text("   \n\n  ") == []
    assert chunk_text("Page 3") == []  # below MIN_CHARS - a page number, not content


# ---------------------------------------------------------------
# Crop resolution (the ask-mode half of the crop guardrail)
# ---------------------------------------------------------------


def test_detects_crop_by_english_name(db_conn):
    with db_conn.cursor() as cur:
        found = crop_lexicon.detect_crops(cur, "How much urea does Cotton need?")
    assert [c["name"] for c in found] == ["Cotton"]


def test_detects_crop_by_hindi_and_marathi_alias(db_conn):
    """The UI runs in three languages; a farmer types कापूस, not "Cotton"."""
    with db_conn.cursor() as cur:
        assert [c["name"] for c in crop_lexicon.detect_crops(cur, "kapas ke liye khad")] == ["Cotton"]
        assert [c["name"] for c in crop_lexicon.detect_crops(cur, "कांदा लागवड")] == ["Onion"]
        assert [c["name"] for c in crop_lexicon.detect_crops(cur, "batata pik")] == ["Potato"]


def test_crop_detection_does_not_fire_on_lookalikes(db_conn):
    """`gram` is a unit far more often than it is a Chickpea, and word
    boundaries must stop a crop name matching inside another word."""
    with db_conn.cursor() as cur:
        assert crop_lexicon.detect_crops(cur, "apply 500 gram per plant") == []
        assert crop_lexicon.detect_crops(cur, "the ricefield was flooded") == []
        assert crop_lexicon.detect_crops(cur, "what fertilizer should I use?") == []


def test_two_crops_are_both_reported_in_order(db_conn):
    with db_conn.cursor() as cur:
        found = crop_lexicon.detect_crops(cur, "Should I plant Soybean or Cotton this year?")
    assert [c["name"] for c in found] == ["Soybean", "Cotton"]


# ---------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------

COTTON, TOMATO = 1, 7


def _insert_chunk(db_conn, *, text, crop_id=None, state_id=None, index=0, vector=None):
    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO document_chunks
                (source_id, chunk_index, chunk_text, crop_id, state_id, embedding, embedding_model)
            VALUES (1, %s, %s, %s, %s, %s::vector, %s)
            RETURNING id
            """,
            (index, text, crop_id, state_id,
             embeddings.to_pgvector(vector) if vector else None,
             EMBEDDING_MODEL if vector else None),
        )
        return cur.fetchone()[0]


def test_retrieval_never_returns_another_crops_chunk(db_conn):
    """The core guardrail. A Cotton question must not see Tomato documents."""
    _insert_chunk(db_conn, text="Cotton needs 80 kg N per hectare." * 3, crop_id=COTTON, index=0)
    _insert_chunk(db_conn, text="Tomato needs staking and 60 kg N." * 3, crop_id=TOMATO, index=1)

    with db_conn.cursor() as cur:
        chunks = retrieval.retrieve(cur, query="nitrogen dose", crop_id=COTTON, district_id=1)

    assert chunks, "the Cotton chunk should have been retrieved"
    assert all(c["crop_id"] in (None, COTTON) for c in chunks)
    assert not any("Tomato" in c["chunk_text"] for c in chunks)


def test_retrieval_admits_crop_agnostic_chunks(db_conn):
    """crop_id NULL means "applies generally", not "unknown" - it is admissible."""
    _insert_chunk(db_conn, text="Soil testing should precede any fertilizer plan." * 3, crop_id=None)
    with db_conn.cursor() as cur:
        chunks = retrieval.retrieve(cur, query="soil testing", crop_id=COTTON, district_id=1)
    assert any(c["crop_id"] is None for c in chunks)


def test_crop_isolation_assertion_catches_a_leak():
    """Second line of defence: if the SQL filter is ever broken, this must
    raise rather than let a wrong-crop chunk through."""
    leaked = [{"crop_id": TOMATO, "chunk_text": "x", "source_id": 1, "id": 1}]
    with pytest.raises(retrieval.CropIsolationError):
        retrieval.assert_crop_isolation(leaked, COTTON)
    # NULL and matching crops are fine.
    retrieval.assert_crop_isolation([{"crop_id": None}, {"crop_id": COTTON}], COTTON)


def test_retrieval_reports_metadata_only_ranking_when_embeddings_are_off(db_conn, monkeypatch):
    monkeypatch.setattr(embeddings, "available", lambda: False)
    _insert_chunk(db_conn, text="Cotton sowing window guidance for Maharashtra." * 3, crop_id=COTTON)
    with db_conn.cursor() as cur:
        chunks = retrieval.retrieve(cur, query="sowing", crop_id=COTTON, district_id=1)
    assert chunks and all(c["ranked_by"] == "metadata" for c in chunks)
    assert all(c["distance"] is None for c in chunks)


def test_vector_ranking_orders_by_distance_and_drops_far_neighbours(db_conn, monkeypatch):
    """Exercises the real pgvector SQL and the relevance pruning."""
    near = [1.0] + [0.0] * (EMBEDDING_DIM - 1)
    far = [0.0, 1.0] + [0.0] * (EMBEDDING_DIM - 2)

    _insert_chunk(db_conn, text="The relevant chunk about cotton nitrogen." * 3,
                  crop_id=COTTON, index=0, vector=near)
    _insert_chunk(db_conn, text="An unrelated chunk about tractor maintenance." * 3,
                  crop_id=COTTON, index=1, vector=far)

    monkeypatch.setattr(embeddings, "available", lambda: True)
    monkeypatch.setattr(embeddings, "embed_query", lambda text: near)

    with db_conn.cursor() as cur:
        chunks = retrieval.retrieve(cur, query="cotton nitrogen", crop_id=COTTON, district_id=1)

    assert chunks[0]["ranked_by"] == "vector"
    assert "relevant chunk" in chunks[0]["chunk_text"]
    # The orthogonal vector sits at distance 1.0 while the match is at 0.0, so
    # it is far outside the relative margin and must be dropped rather than
    # offered as the best available match.
    assert not any("tractor" in c["chunk_text"] for c in chunks)


def test_relevance_pruning_is_relative_to_the_best_match(monkeypatch):
    """The cutoff must scale with the query, not with a hardcoded number: what
    counts as "close" is a property of the embedding model."""
    monkeypatch.setattr(retrieval, "RAG_RELATIVE_MARGIN", 0.15)
    monkeypatch.setattr(retrieval, "RAG_MAX_DISTANCE", 0.9)

    # A genuinely good match set: all three survive because they cluster.
    tight = [{"distance": d} for d in (0.20, 0.28, 0.34)]
    assert len(retrieval._prune(tight)) == 3

    # One clear winner and two stragglers: the stragglers go.
    spread = [{"distance": d} for d in (0.20, 0.62, 0.71)]
    assert [c["distance"] for c in retrieval._prune(spread)] == [0.20]

    # A whole set that is merely "nearest" and not relevant is rejected by the
    # absolute cap, so nothing is offered at all.
    hopeless = [{"distance": d} for d in (0.95, 0.97)]
    assert retrieval._prune(hopeless) == []

    # The same cluster, shifted to the scale a different model might produce -
    # still all kept, which a fixed 0.55 ceiling would have thrown away.
    shifted = [{"distance": d} for d in (0.80, 0.86, 0.88)]
    assert len(retrieval._prune(shifted)) == 3


def test_state_filter_excludes_other_states_but_keeps_general(db_conn):
    _insert_chunk(db_conn, text="Maharashtra specific advisory content here." * 3, state_id=1, index=0)
    _insert_chunk(db_conn, text="Nationally applicable advisory content here." * 3, state_id=None, index=1)
    with db_conn.cursor() as cur:
        chunks = retrieval.retrieve(cur, query="advisory", crop_id=None, district_id=1)
    assert len(chunks) >= 2  # both the state-specific and the general one


# ---------------------------------------------------------------
# Generation — fake Claude client, no network
# ---------------------------------------------------------------


def _citation(document_index: int, cited_text: str = "cited passage"):
    return SimpleNamespace(
        type="char_location", document_index=document_index, cited_text=cited_text,
        document_title="t", start_char_index=0, end_char_index=len(cited_text),
    )


def _fake_response(text: str, citations=None, stop_reason="end_turn"):
    block = SimpleNamespace(type="text", text=text, citations=citations or [])
    return SimpleNamespace(content=[block], stop_reason=stop_reason, model="claude-opus-5")


class _FakeMessages:
    def __init__(self, response):
        self._response = response
        self.captured: dict = {}

    def create(self, **kwargs):
        self.captured = kwargs
        return self._response


def _install_fake(monkeypatch, response):
    """Force the Anthropic backend and hand it a canned response."""
    fake = _FakeMessages(response)
    monkeypatch.setattr(generation, "RAG_PROVIDER", "anthropic")
    monkeypatch.setattr(generation, "RAG_MODEL", "claude-opus-5")
    monkeypatch.setattr(generation, "available", lambda: True)
    monkeypatch.setattr(generation, "_anthropic_client", lambda: SimpleNamespace(messages=fake))
    return fake


class _FakeCompletions:
    """Minimal stand-in for the OpenAI-compatible chat.completions surface."""

    def __init__(self, content: str, raises: Exception | None = None):
        self._content = content
        self._raises = raises
        self.captured: dict = {}

    def create(self, **kwargs):
        self.captured = kwargs
        if self._raises:
            raise self._raises
        message = SimpleNamespace(content=self._content)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=message)], model="llama-3.3-70b-versatile",
        )


def _install_fake_openai(monkeypatch, content: str, raises: Exception | None = None):
    """Force the Groq/Ollama backend and hand it a canned response."""
    fake = _FakeCompletions(content, raises)
    monkeypatch.setattr(generation, "RAG_PROVIDER", "groq")
    monkeypatch.setattr(generation, "RAG_MODEL", "llama-3.3-70b-versatile")
    monkeypatch.setattr(generation, "available", lambda: True)
    monkeypatch.setattr(
        generation, "_openai_client",
        lambda: SimpleNamespace(chat=SimpleNamespace(completions=fake)),
    )
    return fake


CHUNKS = [
    {"id": 11, "source_id": 3, "chunk_text": "Cotton responds to 80 kg N/ha.",
     "crop_id": COTTON, "page_start": 4, "page_end": 4, "chunk_index": 0, "distance": 0.1},
    {"id": 12, "source_id": 5, "chunk_text": "Split the dose at sowing and squaring.",
     "crop_id": COTTON, "page_start": 9, "page_end": 10, "chunk_index": 1, "distance": 0.2},
]


def test_generate_maps_citations_back_to_the_right_source(monkeypatch):
    _install_fake(monkeypatch, _fake_response(
        "Cotton needs about 80 kg N per hectare, split across two applications.",
        citations=[_citation(0, "80 kg N/ha"), _citation(1, "sowing and squaring")],
    ))
    result = generation.generate(question="How much N?", chunks=CHUNKS)

    assert result.grounded and not result.declined and result.generated_by_llm
    assert [c["source_id"] for c in result.citations] == [3, 5]
    assert [c["chunk_id"] for c in result.citations] == [11, 12]
    # Page provenance travels with the citation, so a claim is checkable.
    assert result.citations[1]["page_start"] == 9


def test_generate_declines_when_the_model_cites_nothing(monkeypatch):
    """Rule 1, enforced on the response. Documents were supplied and nothing was
    cited, so the text is untraceable and must not be shown."""
    _install_fake(monkeypatch, _fake_response("Cotton generally likes warm weather."))
    result = generation.generate(question="How much N?", chunks=CHUNKS)

    assert result.declined
    assert "don't have grounded information" in result.answer
    assert "warm weather" not in result.answer
    assert result.citations == []


def test_generate_declines_on_the_no_answer_sentinel(monkeypatch):
    _install_fake(monkeypatch, _fake_response(generation.NO_ANSWER_SENTINEL))
    result = generation.generate(question="What is the price of gold?", chunks=CHUNKS)
    assert result.declined
    assert generation.NO_ANSWER_SENTINEL not in result.answer  # never leaked to the user


def test_generate_declines_on_a_safety_refusal(monkeypatch):
    _install_fake(monkeypatch, _fake_response("", stop_reason="refusal"))
    result = generation.generate(question="anything", chunks=CHUNKS)
    assert result.declined
    assert result.answer  # not a blank explanation


def test_generate_declines_without_calling_the_api_when_nothing_was_retrieved(monkeypatch):
    fake = _install_fake(monkeypatch, _fake_response("should never be produced"))
    result = generation.generate(question="anything", chunks=[])
    assert result.declined
    assert fake.captured == {}, "no documents means there is nothing to ask about"


def test_request_shape_carries_citations_caching_and_the_unverified_block(monkeypatch):
    fake = _install_fake(monkeypatch, _fake_response("answer", citations=[_citation(0)]))
    generation.generate(
        question="How much N?",
        chunks=CHUNKS,
        source_titles={3: "ICAR Cotton Guide", 5: "MPKV Bulletin"},
        computed_context={"opportunity_pct": 46},
        unverified_notes=["nitrogen 80 kg/ha (SYNTHETIC_PLACEHOLDER)"],
    )
    sent = fake.captured
    content = sent["messages"][0]["content"]
    documents = [b for b in content if b["type"] == "document"]

    assert len(documents) == len(CHUNKS)
    assert all(d["citations"] == {"enabled": True} for d in documents)
    assert documents[0]["title"] == "ICAR Cotton Guide"
    assert "page 4" in documents[0]["context"]
    # Cache the [system + documents] prefix; only the question varies per press
    # of the "Why <crop>?" button.
    assert documents[-1]["cache_control"] == {"type": "ephemeral"}
    assert "cache_control" not in documents[0]

    tail = content[-1]["text"]
    assert "UNVERIFIED" in tail and "SYNTHETIC_PLACEHOLDER" in tail
    assert "opportunity_pct" in tail
    assert sent["model"] == "claude-opus-5"


# ---------------------------------------------------------------
# Verified citations — what replaces native citations on Groq/Ollama
# ---------------------------------------------------------------


def test_quote_supported_accepts_real_quotes_and_rejects_invented_ones():
    chunk = ("For rainfed cotton on medium black soils, a general dose of 60 kg nitrogen, "
             "30 kg phosphorus and 30 kg potassium per hectare is applied.")

    # Verbatim, and the same text with whitespace/case mangled.
    assert generation.quote_supported("a general dose of 60 kg nitrogen", chunk)
    assert generation.quote_supported("A GENERAL   dose of 60 kg\n nitrogen", chunk)
    # A model that fixed a small typo should still pass.
    assert generation.quote_supported("a general dose of 60 kg nitrogenn", chunk)

    # Fabricated: plausible, agriculturally sensible, and not in the source.
    assert not generation.quote_supported(
        "apply 120 kg of urea in three equal splits after flowering", chunk,
    )
    # Too short to be evidence of anything.
    assert not generation.quote_supported("60 kg", chunk)
    assert not generation.quote_supported("", chunk)


def test_parse_marker_citations_keeps_verified_quotes_and_strips_markers():
    raw = (
        "Cotton needs about 80 kg of nitrogen [1], split across two applications [2].\n"
        "SOURCES:\n"
        '[1] "Cotton responds to 80 kg N/ha."\n'
        '[2] "Split the dose at sowing and squaring."\n'
    )
    answer, citations = generation.parse_marker_citations(raw, CHUNKS)

    assert "[1]" not in answer and "[2]" not in answer  # markers stripped from prose
    assert answer.startswith("Cotton needs about 80 kg of nitrogen")
    assert [c["source_id"] for c in citations] == [3, 5]
    assert [c["chunk_id"] for c in citations] == [11, 12]
    assert citations[1]["page_start"] == 9  # provenance carried through


@pytest.mark.parametrize(
    ("label", "raw"),
    [
        ("markdown bold header", '**SOURCES:**\n[1] "Cotton responds to 80 kg N/ha."'),
        ("lowercase header", 'Sources:\n[1] "Cotton responds to 80 kg N/ha."'),
        ("content on the header line", 'SOURCES: [1] "Cotton responds to 80 kg N/ha."'),
        ("full-width brackets", 'SOURCES:\n【1】 "Cotton responds to 80 kg N/ha."'),
        ("numbered list style", 'SOURCES:\n1. "Cotton responds to 80 kg N/ha."'),
        ("parenthesised", 'SOURCES:\n(1) "Cotton responds to 80 kg N/ha."'),
        ("curly quotes", "SOURCES:\n[1] “Cotton responds to 80 kg N/ha.”"),
        ("wrapped over two lines", 'SOURCES:\n[1] "Cotton responds to\n80 kg N/ha."'),
        ("no header, quote inline", 'The dose is high. "Cotton responds to 80 kg N/ha."'),
    ],
)
def test_citation_parsing_survives_format_variation(label, raw):
    """Parsing is liberal, verification is strict.

    The regression this guards: the model line-wrapped a long quote, a
    single-line regex found nothing, and a question the corpus plainly answered
    was declined. A false decline is its own harm - it teaches the farmer the
    feature is useless.
    """
    _, citations = generation.parse_marker_citations(f"An answer [1].\n{raw}", CHUNKS)
    assert len(citations) == 1, f"{label}: citation was lost"
    assert citations[0]["source_id"] == 3


def test_liberal_parsing_still_rejects_invention_in_every_format():
    """Loosening the format must not loosen the safety property."""
    fabricated = "Cotton requires 200 kg N/ha applied entirely at flowering."
    for raw in (
        f'**SOURCES:**\n[1] "{fabricated}"',
        f'SOURCES: [1] "{fabricated}"',
        f'SOURCES:\n1. "{fabricated}"',
        f'An answer. "{fabricated}"',            # salvage path
    ):
        _, citations = generation.parse_marker_citations(f"Answer [1].\n{raw}", CHUNKS)
        assert citations == [], f"invented quote accepted via: {raw[:40]}"


def test_inline_quotes_are_stripped_from_the_prose():
    """gpt-oss inlines source sentences despite being told not to; a raw source
    sentence mid-answer reads as a glitch."""
    raw = (
        'Apply half the nitrogen at sowing [1].\n'
        'SOURCES:\n[1] "Cotton responds to 80 kg N/ha."'
    )
    answer, citations = generation.parse_marker_citations(raw, CHUNKS)
    assert answer == "Apply half the nitrogen at sowing."
    assert len(citations) == 1


def test_parse_marker_citations_drops_a_fabricated_quote():
    """The whole point of the verification: a made-up quote is not evidence."""
    raw = (
        "Cotton needs 200 kg of nitrogen [1].\n"
        "SOURCES:\n"
        '[1] "Cotton requires 200 kg N/ha applied entirely at flowering."\n'
    )
    _, citations = generation.parse_marker_citations(raw, CHUNKS)
    assert citations == []


def test_a_misnumbered_citation_is_resolved_to_its_real_source():
    """Document 9 does not exist, but the quote is genuinely from document 1.

    A wrong number attached to a real quote is a numbering slip, not an
    invention, so it resolves to the chunk the text actually came from rather
    than being thrown away. The safety property is unchanged: the quote still
    had to be found in a real chunk.
    """
    _, citations = generation.parse_marker_citations(
        'Answer [9].\nSOURCES:\n[9] "Cotton responds to 80 kg N/ha."\n', CHUNKS,
    )
    assert len(citations) == 1
    assert citations[0]["chunk_id"] == 11  # the chunk that really contains it


def test_no_citation_material_at_all_yields_nothing():
    answer, citations = generation.parse_marker_citations("Just an answer.", CHUNKS)
    assert citations == [] and answer == "Just an answer."
    # A misnumbered citation whose quote is invented is still rejected outright.
    _, citations = generation.parse_marker_citations(
        'Answer [9].\nSOURCES:\n[9] "Cotton needs 500 kg of urea at flowering."\n', CHUNKS,
    )
    assert citations == []


def test_openai_backend_returns_a_grounded_answer_with_verified_citations(monkeypatch):
    _install_fake_openai(monkeypatch, (
        "Cotton needs about 80 kg of nitrogen per hectare [1], split between sowing "
        "and squaring [2].\n"
        "SOURCES:\n"
        '[1] "Cotton responds to 80 kg N/ha."\n'
        '[2] "Split the dose at sowing and squaring."\n'
    ))
    result = generation.generate(question="How much N?", chunks=CHUNKS)

    assert result.grounded and not result.declined and result.generated_by_llm
    assert result.model == "llama-3.3-70b-versatile"
    assert [c["source_id"] for c in result.citations] == [3, 5]
    assert "[1]" not in result.answer


def test_openai_backend_declines_when_every_quote_is_fabricated(monkeypatch):
    """Rule 1 has to hold without native citations, or the free stack is a
    downgrade in safety rather than only in cost."""
    _install_fake_openai(monkeypatch, (
        "Cotton needs 200 kg of nitrogen at flowering [1].\n"
        "SOURCES:\n"
        '[1] "Cotton requires 200 kg N/ha applied entirely at flowering."\n'
    ))
    result = generation.generate(question="How much N?", chunks=CHUNKS)

    assert result.declined
    assert "200 kg" not in result.answer
    assert result.citations == []


def test_openai_backend_declines_when_no_sources_block_is_produced(monkeypatch):
    _install_fake_openai(monkeypatch, "Cotton generally likes warm weather.")
    result = generation.generate(question="How much N?", chunks=CHUNKS)
    assert result.declined and result.citations == []


def test_openai_backend_honours_the_no_answer_sentinel(monkeypatch):
    _install_fake_openai(monkeypatch, generation.NO_ANSWER_SENTINEL)
    result = generation.generate(question="price of gold?", chunks=CHUNKS)
    assert result.declined
    assert generation.NO_ANSWER_SENTINEL not in result.answer


def test_openai_request_numbers_documents_and_asks_for_quotes(monkeypatch):
    fake = _install_fake_openai(monkeypatch, 'x [1]\nSOURCES:\n[1] "Cotton responds to 80 kg N/ha."')
    generation.generate(
        question="How much N?",
        chunks=CHUNKS,
        source_titles={3: "ICAR Cotton Guide", 5: "MPKV Bulletin"},
        computed_context={"opportunity_pct": 46},
        unverified_notes=["nitrogen 80 kg/ha (SYNTHETIC_PLACEHOLDER)"],
    )
    sent = fake.captured
    user = sent["messages"][1]["content"]

    # Documents are numbered from 1, which is what citation markers refer to.
    assert "DOCUMENT 1 (ICAR Cotton Guide, page 4):" in user
    assert "DOCUMENT 2 (MPKV Bulletin, pages 9-10):" in user
    assert "UNVERIFIED" in user and "SYNTHETIC_PLACEHOLDER" in user
    assert "opportunity_pct" in user
    # Grounded extraction, not creative writing.
    assert sent["temperature"] == 0
    assert "SOURCES:" in sent["messages"][0]["content"]


def test_unreachable_backend_raises_rather_than_silently_declining(monkeypatch):
    """An Ollama that isn't running must not look like an empty corpus."""
    _install_fake_openai(monkeypatch, "", raises=ConnectionError("connection refused"))
    with pytest.raises(generation.GenerationError, match="groq"):
        generation.generate(question="How much N?", chunks=CHUNKS)


def test_ask_degrades_to_extractive_when_the_backend_is_down(client, farmer_token, db_conn, monkeypatch):
    """...but the request still succeeds, quoting the retrieved passages."""
    _insert_chunk(db_conn, text="Cotton nitrogen guidance for Maharashtra growers." * 3,
                  crop_id=COTTON, index=0)
    monkeypatch.setattr(generation, "available", lambda: True)
    monkeypatch.setattr(
        generation, "generate",
        lambda **kw: (_ for _ in ()).throw(generation.GenerationError("down")),
    )
    resp = client.post(
        f"{API}/rag/query", headers=auth_header(farmer_token),
        json={"mode": "ask", "question": "Cotton fertilizer advice?", "district_id": 1},
    )
    body = resp.json()
    assert resp.status_code == 200
    assert body["generated_by"] == "extractive"
    assert "Cotton nitrogen guidance" in body["answer"]


def test_extractive_fallback_quotes_rather_than_paraphrases():
    result = generation.extractive_fallback(question="q", chunks=CHUNKS)
    assert not result.generated_by_llm
    assert "80 kg N/ha" in result.answer
    assert [c["source_id"] for c in result.citations] == [3, 5]


# ---------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------


def test_ask_refuses_to_answer_a_two_crop_question(client, farmer_token, db_conn):
    """Answering "Soybean or Cotton?" from one crop's documents would break the
    isolation rule while looking like it worked."""
    resp = client.post(
        f"{API}/rag/query", headers=auth_header(farmer_token),
        json={"mode": "ask", "question": "Should I plant Soybean or Cotton?", "district_id": 1},
    )
    body = resp.json()
    assert resp.status_code == 200
    assert body["declined"] is True
    assert "one crop at a time" in body["answer"]
    assert [c["name"] for c in body["crops_detected"]] == ["Soybean", "Cotton"]
    assert body["sources"] == []


def test_ask_about_one_crop_never_surfaces_another_crops_source(client, farmer_token, db_conn):
    _insert_chunk(db_conn, text="Cotton nitrogen guidance for Maharashtra growers." * 3,
                  crop_id=COTTON, index=0)
    _insert_chunk(db_conn, text="Tomato staking guidance for Maharashtra growers." * 3,
                  crop_id=TOMATO, index=1)

    resp = client.post(
        f"{API}/rag/query", headers=auth_header(farmer_token),
        json={"mode": "ask", "question": "Cotton fertilizer advice?", "district_id": 1},
    )
    body = resp.json()
    assert "Tomato" not in body["answer"]
    assert [c["name"] for c in body["crops_detected"]] == ["Cotton"]
    assert body["retrieval"] in {"vector", "metadata"}


def test_explain_still_answers_with_an_empty_corpus(client, farmer_token, db_conn):
    """Explain mode is grounded in database columns, not documents, so it must
    not decline just because nothing has been ingested yet."""
    with db_conn.cursor() as cur:
        cur.execute("DELETE FROM document_chunks")

    resp = client.post(
        f"{API}/rag/query", headers=auth_header(farmer_token),
        json={"mode": "explain", "crop_id": TOMATO, "district_id": 1,
              "computed_context": {"opportunity_pct": 46}},
    )
    body = resp.json()
    assert resp.status_code == 200
    assert body["declined"] is False
    assert "Tomato" in body["answer"] and "46%" in body["answer"]
    assert body["generated_by"] == "template"
    assert body["retrieval"] == "none"


def test_explain_flags_unverified_doses_from_the_data_not_the_model(client, farmer_token):
    """`used_placeholder_data` is computed from fertilizer_recommendations.
    is_verified, so it stays correct even if the answer text omits the warning."""
    resp = client.post(
        f"{API}/rag/query", headers=auth_header(farmer_token),
        json={"mode": "explain", "crop_id": TOMATO, "district_id": 1, "computed_context": {}},
    )
    body = resp.json()
    assert body["used_placeholder_data"] is True
    assert "unverified" in body["answer"].lower()


def test_unverified_notes_only_fire_for_unverified_rows(db_conn):
    with db_conn.cursor() as cur:
        unverified = rag.get_fertilizer_guidance(cur, TOMATO)
        assert unverified and unverified["is_verified"] is False
        assert rag._unverified_notes(unverified), "an unverified row must produce notes"
        # A verified row is ordinary data and needs no special block.
        assert rag._unverified_notes({**unverified, "is_verified": True}) == []
        assert rag._unverified_notes(None) == []


def test_status_reports_what_is_actually_wired_up(client, farmer_token, db_conn):
    with db_conn.cursor() as cur:
        cur.execute("DELETE FROM document_chunks")
    resp = client.get(f"{API}/rag/status", headers=auth_header(farmer_token))
    body = resp.json()
    assert resp.status_code == 200
    assert body["chunks"] == 0
    assert body["readiness"] == "no corpus ingested"
    # Whatever the local environment has, the flags must describe it truthfully.
    assert body["generation_available"] is generation.available()
    assert body["embeddings_available"] is embeddings.available()


def test_status_requires_authentication(client):
    assert client.get(f"{API}/rag/status").status_code == 401
