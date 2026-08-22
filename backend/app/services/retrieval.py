"""Two-stage retrieval over `document_chunks`.

Stage 1 is a metadata filter, stage 2 ranks what survives by vector distance.
That order matters and is not an optimisation: it is how the crop guardrail is
enforced. Ranking first and filtering after would mean a Cotton question whose
nearest neighbours are all Tomato chunks returns nothing useful, or worse,
returns them because someone later "fixed" the empty result by relaxing the
filter. Filtering first makes the guarantee structural.

Crop isolation, precisely:

    crop_id = <asked crop>  ->  admissible (documents about this crop)
    crop_id IS NULL         ->  admissible (general agronomy, applies to any crop)
    crop_id = <other crop>  ->  never admissible

The third case is excluded by the SQL and then checked again in Python before
anything is returned. The duplication is intentional - the SQL is built by
string concatenation, and a future edit to the WHERE clause that drops the crop
predicate would silently disable the whole guardrail. The assertion turns that
into a loud failure instead of a wrong answer.

When embeddings are unavailable (no VOYAGE_API_KEY, or the corpus was ingested
without vectors) stage 2 degrades to deterministic `chunk_index` order over the
filtered set, and every result is marked `ranked_by="metadata"` so callers can
say so rather than implying a semantic match happened.
"""

from __future__ import annotations

from typing import Any

from psycopg import Cursor

from ..config import EMBEDDING_MODEL, RAG_MAX_DISTANCE, RAG_RELATIVE_MARGIN, RAG_TOP_K
from . import embeddings


class CropIsolationError(RuntimeError):
    """A chunk for a different crop reached the caller. Always a bug."""


def _state_of(cur: Cursor, district_id: int | None) -> int | None:
    if district_id is None:
        return None
    cur.execute("SELECT state_id FROM districts WHERE id = %s", (district_id,))
    row = cur.fetchone()
    return row[0] if row else None


def _filters(crop_id: int | None, state_id: int | None, season_id: int | None) -> tuple[str, list[Any]]:
    """The stage-1 predicate.

    NULL on a chunk means "applies generally", so each filter admits its own
    value OR NULL. Omitting a filter entirely (None argument) admits everything
    for that column - that is "we were not told", which is different from the
    chunk saying "any".
    """
    clauses = ["chunk_text <> ''"]
    params: list[Any] = []
    if crop_id is not None:
        clauses.append("(crop_id = %s OR crop_id IS NULL)")
        params.append(crop_id)
    if state_id is not None:
        clauses.append("(state_id = %s OR state_id IS NULL)")
        params.append(state_id)
    if season_id is not None:
        clauses.append("(season_id = %s OR season_id IS NULL)")
        params.append(season_id)
    return " AND ".join(clauses), params


def _rows_to_chunks(rows: list[tuple], *, ranked_by: str) -> list[dict[str, Any]]:
    return [
        {
            "id": row[0],
            "source_id": row[1],
            "chunk_text": row[2],
            "crop_id": row[3],
            "page_start": row[4],
            "page_end": row[5],
            "chunk_index": row[6],
            "distance": float(row[7]) if len(row) > 7 and row[7] is not None else None,
            "ranked_by": ranked_by,
        }
        for row in rows
    ]


SELECT_COLUMNS = "id, source_id, chunk_text, crop_id, page_start, page_end, chunk_index"


def _prune(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop neighbours that are only "nearest", not relevant.

    In any corpus the closest chunk to a question exists; that is not the same
    as it answering the question, and passing it on unchallenged is how "no
    source found" would turn into a fabrication.

    Filtering is relative to the best match for this query rather than against
    one absolute number, because what counts as "close" depends on the
    embedding model and on how long the texts are. An absolute threshold tuned
    against one model drops everything under another - and it fails silently,
    looking exactly like a corpus nobody ingested. The absolute cap stays only
    as a guard against the actively unrelated.
    """
    scored = [c for c in chunks if c["distance"] is not None]
    if not scored:
        return []
    best = min(c["distance"] for c in scored)
    ceiling = min(RAG_MAX_DISTANCE, best + RAG_RELATIVE_MARGIN)
    return [c for c in scored if c["distance"] <= ceiling]


def retrieve(
    cur: Cursor,
    *,
    query: str | None,
    crop_id: int | None,
    district_id: int | None = None,
    season_id: int | None = None,
    top_k: int = RAG_TOP_K,
) -> list[dict[str, Any]]:
    """Chunks admissible for this question, best first.

    An empty list is a legitimate and common answer - the caller must decline
    rather than widen the filters.
    """
    state_id = _state_of(cur, district_id)
    where, params = _filters(crop_id, state_id, season_id)

    use_vectors = bool(query) and embeddings.available()
    if use_vectors:
        try:
            vector = embeddings.to_pgvector(embeddings.embed_query(query))
        except embeddings.EmbeddingError:
            # A retriever that answers from an arbitrary slice of the corpus is
            # worse than one that admits it is degraded, but refusing outright
            # would take the whole feature down over a transient 429.
            use_vectors = False

    if use_vectors:
        # embedding_model is part of the filter, not decoration: vectors from a
        # different model are not comparable to this query's vector, and the
        # symptom would be plausible-looking wrong neighbours.
        cur.execute(
            f"""
            SELECT {SELECT_COLUMNS}, embedding <=> %s::vector AS distance
            FROM document_chunks
            WHERE {where}
              AND embedding IS NOT NULL
              AND embedding_model = %s
            ORDER BY distance
            LIMIT %s
            """,
            [vector, *params, EMBEDDING_MODEL, top_k],
        )
        chunks = _prune(_rows_to_chunks(cur.fetchall(), ranked_by="vector"))
    else:
        cur.execute(
            f"""
            SELECT {SELECT_COLUMNS}
            FROM document_chunks
            WHERE {where}
            ORDER BY source_id, chunk_index
            LIMIT %s
            """,
            [*params, top_k],
        )
        chunks = _rows_to_chunks(cur.fetchall(), ranked_by="metadata")

    return assert_crop_isolation(chunks, crop_id)


def assert_crop_isolation(chunks: list[dict[str, Any]], crop_id: int | None) -> list[dict[str, Any]]:
    """Second enforcement of the crop rule. See the module docstring."""
    if crop_id is None:
        return chunks
    leaked = {c["crop_id"] for c in chunks if c["crop_id"] not in (None, crop_id)}
    if leaked:
        raise CropIsolationError(
            f"retrieval for crop {crop_id} returned chunks for crops {sorted(leaked)} - "
            f"the stage-1 metadata filter is not doing its job",
        )
    return chunks


def get_sources(cur: Cursor, source_ids: set[int]) -> list[dict[str, Any]]:
    """Bibliographic detail for the retrieved chunks.

    Returns title and url alongside organization: "cite your sources" is not
    satisfied by an organisation name the reader cannot look up.
    """
    if not source_ids:
        return []
    cur.execute(
        """
        SELECT id, organization, title, url, source_type, publication_date
        FROM sources WHERE id = ANY(%s)
        ORDER BY id
        """,
        (sorted(source_ids),),
    )
    return [
        {
            "source_id": row[0],
            "organization": row[1],
            "title": row[2],
            "url": row[3],
            "source_type": row[4],
            "publication_date": row[5].isoformat() if row[5] else None,
        }
        for row in cur.fetchall()
    ]


def corpus_stats(cur: Cursor) -> dict[str, Any]:
    """What the corpus actually contains - powers GET /rag/status."""
    cur.execute(
        """
        SELECT count(*), count(embedding), count(DISTINCT source_id),
               count(DISTINCT embedding_model)
        FROM document_chunks
        """,
    )
    total, embedded, sources, models = cur.fetchone()
    return {
        "chunks": total,
        "chunks_embedded": embedded,
        "sources_indexed": sources,
        "embedding_models_present": models,
    }
