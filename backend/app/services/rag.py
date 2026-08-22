"""RAG orchestration: retrieve, then explain, then report honestly which.

Two entry points, and the difference between them is not cosmetic.

`answer_explain` is the "Why <crop>?" button. The caller already knows the crop
and district, so the crop guardrail is satisfied by construction, and the
platform's own computed figures (opportunity score, demand gap) are real data
that exists whether or not any document has been ingested. So explain mode
still answers with no corpus - from the database, deterministically - and gets
*better* when documents exist. It never declines for lack of a corpus, because
the numbers are not the thing that needed a source.

`answer_ask` is the free-text box. Nothing is known up front, so the crop has
to be recovered from the question text before anything can be retrieved (see
`crop_lexicon`). With no crop found, only crop-agnostic sources are admissible;
with two crops found, it refuses rather than answering one crop's question from
the other's documents.

Every response carries how it was produced - `generated_by` and `retrieval` -
so a thin answer is attributable to a missing key, an unreachable backend or an
empty corpus instead of looking like a bad model. When a backend fails at
transport level the error is recorded and surfaced by GET /rag/status, because
degrading silently is how a retired model went unnoticed once already.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from psycopg import Cursor

from . import crop_lexicon, embeddings, generation, retrieval


@dataclass
class RagAnswer:
    answer: str
    sources: list[dict[str, Any]] = field(default_factory=list)
    citations: list[dict[str, Any]] = field(default_factory=list)
    used_placeholder_data: bool = False
    grounded: bool = False
    declined: bool = False
    # "model" | "template" | "extractive" - which code path wrote the text.
    generated_by: str = "template"
    # "vector" | "metadata" | "none" - how the chunks were ranked.
    retrieval: str = "none"
    crops_detected: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------
# Database facts the answer may be grounded in
# ---------------------------------------------------------------


def get_market_snapshot(cur: Cursor, district_id: int, crop_id: int) -> dict[str, Any] | None:
    cur.execute(
        """
        SELECT expected_demand_qty, expected_supply_qty, demand_gap, unit, year
        FROM crop_market_data
        WHERE district_id = %s AND crop_id = %s
        ORDER BY year DESC
        LIMIT 1
        """,
        (district_id, crop_id),
    )
    row = cur.fetchone()
    if row is None:
        return None
    demand, supply, gap, unit, year = row
    return {
        "expected_demand_qty": float(demand) if demand is not None else None,
        "expected_supply_qty": float(supply) if supply is not None else None,
        "demand_gap": float(gap) if gap is not None else None,
        "unit": unit,
        "year": year,
    }


def get_fertilizer_guidance(cur: Cursor, crop_id: int) -> dict[str, Any] | None:
    """Dose guidance, verified rows preferred.

    Returns the numbers, not just the flag, because the model can only be
    required to label an unverified figure if it was given the figure.
    """
    cur.execute(
        """
        SELECT is_verified, source_id, nitrogen_kg_ha, phosphorus_kg_ha,
               potassium_kg_ha, application_stage, recommendation_text, data_source
        FROM fertilizer_recommendations
        WHERE crop_id = %s
        ORDER BY is_verified DESC, id
        LIMIT 1
        """,
        (crop_id,),
    )
    row = cur.fetchone()
    if row is None:
        return None
    return {
        "is_verified": row[0],
        "source_id": row[1],
        "nitrogen_kg_ha": float(row[2]) if row[2] is not None else None,
        "phosphorus_kg_ha": float(row[3]) if row[3] is not None else None,
        "potassium_kg_ha": float(row[4]) if row[4] is not None else None,
        "application_stage": row[5],
        "recommendation_text": row[6],
        "data_source": row[7],
    }


def get_sources(cur: Cursor, source_ids: set[int]) -> list[dict[str, Any]]:
    return retrieval.get_sources(cur, source_ids)


def _unverified_notes(guidance: dict[str, Any] | None) -> list[str]:
    """Dose figures rendered for the model, only when they are NOT verified.

    Verified numbers need no special handling; unverified ones go into the
    prompt's UNVERIFIED block so any answer touching them must say so.
    """
    if not guidance or guidance["is_verified"]:
        return []
    notes = []
    for label, key in (
        ("nitrogen", "nitrogen_kg_ha"),
        ("phosphorus", "phosphorus_kg_ha"),
        ("potassium", "potassium_kg_ha"),
    ):
        if guidance[key] is not None:
            notes.append(f"{label} {guidance[key]:g} kg/ha ({guidance['data_source']})")
    if guidance["application_stage"]:
        notes.append(f"application stage: {guidance['application_stage']}")
    if guidance["recommendation_text"]:
        notes.append(str(guidance["recommendation_text"]))
    return notes


def _source_titles(sources: list[dict[str, Any]]) -> dict[int, str]:
    return {
        s["source_id"]: (s.get("title") or s.get("organization") or f"Source {s['source_id']}")
        for s in sources
    }


def _retrieval_mode(chunks: list[dict[str, Any]]) -> str:
    if not chunks:
        return "none"
    return chunks[0].get("ranked_by") or "metadata"


# ---------------------------------------------------------------
# Explain mode
# ---------------------------------------------------------------


def _template_explanation(
    crop_name: str,
    district_name: str,
    market: dict[str, Any] | None,
    computed_context: dict[str, Any],
    guidance: dict[str, Any] | None,
) -> str:
    """The no-LLM answer: database figures, stated plainly, nothing inferred.

    This is what ships before a corpus exists and before ANTHROPIC_API_KEY is
    set. It says less than Claude would, but every clause traces to a column.
    """
    parts = [f"For {crop_name} in {district_name}:"]
    if market and market["expected_demand_qty"] is not None and market["expected_supply_qty"] is not None:
        unit = market["unit"] or "units"
        gap = computed_context.get("demand_gap", market["demand_gap"])
        if gap is not None:
            parts.append(
                f"expected demand is {market['expected_demand_qty']:g} {unit}, "
                f"expected supply is {market['expected_supply_qty']:g} {unit}, "
                f"giving a demand gap of {gap:g} {unit}.",
            )
        else:
            parts.append("expected demand/supply figures aren't available yet.")

    opportunity = computed_context.get("opportunity_pct")
    if opportunity is not None:
        parts.append(f"This contributes to an opportunity score of {opportunity}%.")

    if guidance and not guidance["is_verified"]:
        parts.append(
            "Fertilizer dose figures for this crop are unverified placeholders - "
            "confirm them with a local agricultural officer before acting.",
        )
    return " ".join(parts)


def answer_explain(
    cur: Cursor,
    *,
    crop_id: int,
    district_id: int,
    computed_context: dict[str, Any] | None,
) -> RagAnswer:
    cur.execute("SELECT name FROM crops WHERE id = %s", (crop_id,))
    crop_row = cur.fetchone()
    cur.execute("SELECT name FROM districts WHERE id = %s", (district_id,))
    district_row = cur.fetchone()
    if crop_row is None or district_row is None:
        return RagAnswer(answer="Unknown crop or district - nothing to explain.", declined=True)

    crop_name, district_name = crop_row[0], district_row[0]
    computed_context = computed_context or {}
    market = get_market_snapshot(cur, district_id, crop_id)
    guidance = get_fertilizer_guidance(cur, crop_id)
    unverified = _unverified_notes(guidance)
    # The flag is set from the data, never from whether the model remembered to
    # mention it - so it stays true even if the sentence is missing.
    used_placeholder = bool(guidance and not guidance["is_verified"])

    chunks = retrieval.retrieve(
        cur,
        query=f"Why grow {crop_name} in {district_name}? Demand, weather suitability and agronomy.",
        crop_id=crop_id,
        district_id=district_id,
    )
    source_ids = {c["source_id"] for c in chunks if c["source_id"] is not None}
    if guidance and guidance["source_id"]:
        source_ids.add(guidance["source_id"])
    sources = get_sources(cur, source_ids)

    context: dict[str, Any] = {f"{crop_name} in {district_name}": "the crop and district being explained"}
    context.update({k: v for k, v in computed_context.items() if v is not None})
    if market:
        context.update(
            {
                "expected_demand": f"{market['expected_demand_qty']:g} {market['unit'] or ''}".strip()
                if market["expected_demand_qty"] is not None
                else None,
                "expected_supply": f"{market['expected_supply_qty']:g} {market['unit'] or ''}".strip()
                if market["expected_supply_qty"] is not None
                else None,
                "demand_gap": market["demand_gap"],
                "market_data_year": market["year"],
            },
        )
    context = {k: v for k, v in context.items() if v is not None}

    if chunks and generation.available():
        try:
            result = generation.generate(
                question=f"Why is {crop_name} a good or poor choice in {district_name} right now?",
                chunks=chunks,
                source_titles=_source_titles(sources),
                computed_context=context,
                unverified_notes=unverified,
            )
        except generation.GenerationError:
            # Backend unreachable (Ollama not running, Groq down). The database
            # figures below are unaffected, so answer from those rather than
            # failing the request.
            result = None

        # A decline means the documents did not support a narrative. The figures
        # are still real, so fall through to them rather than telling a farmer
        # we know nothing.
        if result is not None and not result.declined:
            return RagAnswer(
                answer=result.answer,
                sources=sources,
                citations=result.citations,
                used_placeholder_data=used_placeholder,
                grounded=result.grounded,
                generated_by="model",
                retrieval=_retrieval_mode(chunks),
            )

    return RagAnswer(
        answer=_template_explanation(crop_name, district_name, market, computed_context, guidance),
        sources=sources,
        used_placeholder_data=used_placeholder,
        # Grounded in database columns rather than in documents - true, but a
        # different kind of grounding, which `generated_by` distinguishes.
        grounded=bool(market or computed_context),
        generated_by="template",
        retrieval=_retrieval_mode(chunks),
    )


# ---------------------------------------------------------------
# Ask mode
# ---------------------------------------------------------------

AMBIGUOUS_CROPS = (
    "That question mentions {names}. I answer about one crop at a time, because "
    "mixing sources across crops produces advice that is wrong for both - please "
    "ask about one of them."
)


def answer_ask(cur: Cursor, *, question: str, district_id: int | None) -> RagAnswer:
    crops = crop_lexicon.detect_crops(cur, question)

    # Refuse rather than choose. Answering a two-crop question from one crop's
    # documents would break the isolation rule while appearing to succeed.
    if len(crops) > 1:
        names = " and ".join(c["name"] for c in crops)
        return RagAnswer(
            answer=AMBIGUOUS_CROPS.format(names=names),
            declined=True,
            crops_detected=crops,
        )

    crop_id = crops[0]["id"] if crops else None
    chunks = retrieval.retrieve(cur, query=question, crop_id=crop_id, district_id=district_id)
    sources = get_sources(cur, {c["source_id"] for c in chunks if c["source_id"] is not None})

    guidance = get_fertilizer_guidance(cur, crop_id) if crop_id else None
    unverified = _unverified_notes(guidance)

    result = None
    generated_by = "extractive"
    if generation.available():
        try:
            result = generation.generate(
                question=question,
                chunks=chunks,
                source_titles=_source_titles(sources),
                unverified_notes=unverified,
            )
            generated_by = "model"
        except generation.GenerationError:
            # Backend unreachable. Quoting the retrieved passages is still a
            # useful, grounded answer - better than a 500.
            result = None
    if result is None:
        result = generation.extractive_fallback(question=question, chunks=chunks)
        generated_by = "extractive"

    return RagAnswer(
        answer=result.answer,
        # A declined answer cites nothing, so listing sources next to it would
        # imply support that was not used.
        sources=[] if result.declined else sources,
        citations=result.citations,
        # Only true if the model was actually handed unverified figures, which
        # requires it to have had documents to answer from in the first place.
        used_placeholder_data=bool(unverified) and not result.declined,
        grounded=result.grounded,
        declined=result.declined,
        generated_by=generated_by,
        retrieval=_retrieval_mode(chunks),
        crops_detected=crops,
    )


# ---------------------------------------------------------------
# Status
# ---------------------------------------------------------------


def status(cur: Cursor) -> dict[str, Any]:
    """What is actually wired up right now.

    Exists so an unhelpful answer can be diagnosed without reading the logs:
    an empty corpus, a missing embeddings key and a missing generation key all
    look identical from the outside otherwise.
    """
    stats = retrieval.corpus_stats(cur)
    llm = generation.available()
    embed = embeddings.available()
    if not stats["chunks"]:
        readiness = "no corpus ingested"
    elif not embed:
        readiness = "corpus present, metadata-only retrieval (embedding provider not configured)"
    elif not stats["chunks_embedded"]:
        readiness = "corpus present but not embedded - re-run rag/ingest.py"
    elif not llm:
        readiness = "retrieval live, answers are extractive (generation provider not configured)"
    else:
        readiness = "fully operational"
    return {
        **stats,
        "generation_model": generation.describe() if llm else None,
        "generation_available": llm,
        # Claude reports citations itself; every other backend has its quotes
        # verified against the source text instead. Worth surfacing, because it
        # is the difference between two strengths of the same guarantee.
        "native_citations": llm and generation.uses_native_citations(),
        "embedding_model": embeddings.describe() if embed else None,
        "embeddings_available": embed,
        # available() reports what is CONFIGURED; only an actual request proves
        # the model name and key work. A retired model made every answer degrade
        # silently once - this is so the next one is visible.
        "last_generation_error": generation.last_error(),
        "readiness": readiness,
    }
