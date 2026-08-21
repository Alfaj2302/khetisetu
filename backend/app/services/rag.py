"""RAG retrieval + answer construction.

No LLM API key or embeddings pipeline exists in this project yet, and
`document_chunks` is unpopulated — that's a later phase of the RAG dev plan.
This module implements the honest interim: metadata-filtered retrieval
against `document_chunks` (works once that table has rows) and a
template-built answer grounded only in retrieved chunks, the caller-supplied
`computed_context`, and real DB values — never independently reasoned, and
explicit when nothing was found, per the guardrail in the API spec.
"""

from __future__ import annotations

from typing import Any

from psycopg import Cursor


def retrieve_chunks(cur: Cursor, *, crop_id: int | None, district_id: int | None) -> list[dict[str, Any]]:
    state_id = None
    if district_id is not None:
        cur.execute("SELECT state_id FROM districts WHERE id = %s", (district_id,))
        row = cur.fetchone()
        state_id = row[0] if row else None

    conditions = []
    params: list[Any] = []
    if crop_id is not None:
        conditions.append("(crop_id = %s OR crop_id IS NULL)")
        params.append(crop_id)
    if state_id is not None:
        conditions.append("(state_id = %s OR state_id IS NULL)")
        params.append(state_id)
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    # Metadata filter only — no embedding similarity search, since no
    # embedding model is wired up to embed the query text yet (RAG dev plan
    # phase 2). Once it is, add `ORDER BY embedding <=> %s LIMIT k` here.
    cur.execute(f"SELECT id, source_id, chunk_text FROM document_chunks {where} ORDER BY id LIMIT 5", params)
    return [{"id": r[0], "source_id": r[1], "chunk_text": r[2]} for r in cur.fetchall()]


def get_fertilizer_guidance(cur: Cursor, crop_id: int) -> dict[str, Any] | None:
    cur.execute(
        """
        SELECT is_verified, source_id
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
    is_verified, source_id = row
    return {"is_verified": is_verified, "source_id": source_id}


def get_market_snapshot(cur: Cursor, district_id: int, crop_id: int) -> dict[str, Any] | None:
    cur.execute(
        """
        SELECT expected_demand_qty, expected_supply_qty, demand_gap, unit
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
    demand, supply, gap, unit = row
    return {
        "expected_demand_qty": float(demand) if demand is not None else None,
        "expected_supply_qty": float(supply) if supply is not None else None,
        "demand_gap": float(gap) if gap is not None else None,
        "unit": unit,
    }


def get_sources(cur: Cursor, source_ids: set[int]) -> list[dict[str, Any]]:
    if not source_ids:
        return []
    cur.execute("SELECT id, organization FROM sources WHERE id = ANY(%s)", (list(source_ids),))
    return [{"source_id": r[0], "organization": r[1]} for r in cur.fetchall()]


def answer_explain(
    cur: Cursor,
    *,
    crop_id: int,
    district_id: int,
    computed_context: dict[str, Any] | None,
) -> tuple[str, list[dict[str, Any]], bool]:
    cur.execute("SELECT name FROM crops WHERE id = %s", (crop_id,))
    crop_row = cur.fetchone()
    cur.execute("SELECT name FROM districts WHERE id = %s", (district_id,))
    district_row = cur.fetchone()
    if crop_row is None or district_row is None:
        return "Unknown crop or district — nothing to explain.", [], False

    crop_name, district_name = crop_row[0], district_row[0]
    computed_context = computed_context or {}
    market = get_market_snapshot(cur, district_id, crop_id)
    guidance = get_fertilizer_guidance(cur, crop_id)

    if not market and not guidance and not computed_context:
        return (
            f"No grounded information is available yet for {crop_name} in {district_name}.",
            [],
            False,
        )

    opportunity_pct = computed_context.get("opportunity_pct")
    demand_gap = computed_context.get("demand_gap", market["demand_gap"] if market else None)

    parts = [f"For {crop_name} in {district_name}:"]
    if market and market["expected_demand_qty"] is not None and market["expected_supply_qty"] is not None:
        unit = market["unit"] or "units"
        parts.append(
            f"expected demand is {market['expected_demand_qty']:g} {unit}, "
            f"expected supply is {market['expected_supply_qty']:g} {unit}, "
            f"giving a demand gap of {demand_gap:g} {unit}."
            if demand_gap is not None
            else "expected demand/supply figures aren't available yet.",
        )
    if opportunity_pct is not None:
        parts.append(f"This contributes to an opportunity score of {opportunity_pct}%.")

    used_placeholder_data = bool(guidance and not guidance["is_verified"])
    source_ids = {guidance["source_id"]} if guidance and guidance["source_id"] else set()

    return " ".join(parts), get_sources(cur, source_ids), used_placeholder_data


def answer_ask(cur: Cursor, *, question: str, district_id: int | None) -> tuple[str, list[dict[str, Any]], bool]:
    chunks = retrieve_chunks(cur, crop_id=None, district_id=district_id)
    if not chunks:
        return (
            f'I don\'t have grounded information to answer "{question}" yet — '
            "no verified source documents have been indexed for this topic.",
            [],
            False,
        )
    source_ids = {c["source_id"] for c in chunks if c["source_id"] is not None}
    answer = " ".join(c["chunk_text"] for c in chunks)
    return answer, get_sources(cur, source_ids), False
