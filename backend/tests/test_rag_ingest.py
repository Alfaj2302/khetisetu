"""The ingest half: source registration, embedding reuse, and the write.

Embedding is faked, so these run offline and cost nothing - but every INSERT,
the pgvector cast, and the CHECK constraint are real, because the failure modes
worth guarding are all in the SQL:

* a re-ingest that leaves orphaned chunks from a longer previous version, which
  keep answering queries;
* an unknown --crop resolving to NULL, which silently converts a one-crop
  document into one admissible for every crop;
* re-embedding text that has not changed, which is just money.
"""

from __future__ import annotations

from argparse import Namespace
from pathlib import Path

import pytest

from app.config import EMBEDDING_DIM, EMBEDDING_MODEL
from app.services import embeddings
from rag import ingest
from rag.chunk import chunk_text

COTTON = 1


def _vector(seed: int) -> list[float]:
    v = [0.0] * EMBEDDING_DIM
    v[seed % EMBEDDING_DIM] = 1.0
    return v


def _args(**overrides) -> Namespace:
    base = dict(
        crop=None, state=None, season=None, product=None,
        source_id=None, organization="TEST ORG", title="Test Doc", url=None,
        source_type="RESEARCH_PUBLICATION", write=True,
    )
    base.update(overrides)
    return Namespace(**base)


@pytest.fixture()
def doc(tmp_path) -> Path:
    path = tmp_path / "cotton-guidance.md"
    path.write_text(
        "\n\n".join(
            f"Section {i}. Cotton nutrient guidance for Maharashtra growers, "
            f"covering nitrogen splitting and soil testing in detail. " * 4
            for i in range(4)
        ),
        encoding="utf-8",
    )
    return path


@pytest.fixture()
def fake_embedder(monkeypatch):
    """Deterministic vectors, and a call counter so reuse is provable."""
    calls: list[int] = []

    def embed_documents(texts: list[str]) -> list[list[float]]:
        calls.append(len(texts))
        return [_vector(i) for i in range(len(texts))]

    monkeypatch.setattr(embeddings, "available", lambda: True)
    monkeypatch.setattr(embeddings, "embed_documents", embed_documents)
    monkeypatch.setattr(ingest.embeddings, "available", lambda: True)
    monkeypatch.setattr(ingest.embeddings, "embed_documents", embed_documents)
    return calls


# ---------------------------------------------------------------
# Metadata resolution — the crop guardrail, ingest side
# ---------------------------------------------------------------


def test_unknown_crop_is_rejected_rather_than_silently_ignored(db_conn):
    """A typo must not become crop_id NULL. NULL means "applies to every crop",
    so accepting it would make a Cotton document answer Tomato questions."""
    with db_conn.cursor() as cur:
        with pytest.raises(SystemExit) as exc:
            ingest._lookup(cur, "crops", "name", "Cottonn")
        assert "unknown crop" in str(exc.value)
        assert "Cotton" in str(exc.value)  # lists the valid values

        assert ingest._lookup(cur, "crops", "name", "cotton") == COTTON  # case-insensitive
        assert ingest._lookup(cur, "crops", "name", None) is None       # omitted is legitimate


def test_ensure_source_reuses_an_identical_row(db_conn):
    with db_conn.cursor() as cur:
        first = ingest.ensure_source(
            cur, source_id=None, organization="ICAR", title="Cotton Guide",
            url="http://x", source_type="RESEARCH_PUBLICATION",
        )
        second = ingest.ensure_source(
            cur, source_id=None, organization="ICAR", title="Cotton Guide",
            url="http://x", source_type="RESEARCH_PUBLICATION",
        )
    assert first == second, "re-running ingest must not accumulate duplicate sources"


def test_ensure_source_rejects_a_missing_source_id(db_conn):
    with db_conn.cursor() as cur, pytest.raises(SystemExit):
        ingest.ensure_source(
            cur, source_id=999999, organization=None, title=None, url=None,
            source_type="RESEARCH_PUBLICATION",
        )


# ---------------------------------------------------------------
# Reading
# ---------------------------------------------------------------


def test_unsupported_file_type_is_refused(tmp_path):
    path = tmp_path / "notes.docx"
    path.write_text("x", encoding="utf-8")
    with pytest.raises(SystemExit, match="unsupported type"):
        ingest.read_pages(path)


def test_markdown_is_read_as_one_page(doc):
    pages = ingest.read_pages(doc)
    assert len(pages) == 1 and pages[0].number == 1
    assert "Cotton nutrient guidance" in pages[0].text


# ---------------------------------------------------------------
# Writing
# ---------------------------------------------------------------


def test_write_chunks_persists_metadata_and_a_queryable_vector(db_conn, doc):
    chunks = chunk_text(doc.read_text())
    assert len(chunks) >= 2
    vectors = [embeddings.to_pgvector(_vector(i)) for i in range(len(chunks))]

    with db_conn.cursor() as cur:
        source_id = ingest.ensure_source(
            cur, source_id=None, organization="TEST", title="T", url=None,
            source_type="RESEARCH_PUBLICATION",
        )
        ingest.write_chunks(
            cur, source_id=source_id, chunks=chunks, vectors=vectors,
            crop_id=COTTON, state_id=1, season_id=None, product_id=None,
        )
        cur.execute(
            """
            SELECT crop_id, state_id, embedding_model, page_start, token_count,
                   content_sha256, vector_dims(embedding)
            FROM document_chunks WHERE source_id = %s ORDER BY chunk_index
            """,
            (source_id,),
        )
        rows = cur.fetchall()

    assert len(rows) == len(chunks)
    assert all(r[0] == COTTON and r[1] == 1 for r in rows)
    assert all(r[2] == EMBEDDING_MODEL for r in rows)          # CHECK constraint satisfied
    assert all(r[3] == 1 for r in rows)                        # page provenance
    assert all(r[4] > 0 and len(r[5]) == 64 for r in rows)
    assert all(r[6] == EMBEDDING_DIM for r in rows)            # width matches the column


def test_reingest_replaces_rather_than_orphaning_old_chunks(db_conn, doc, fake_embedder):
    """A shorter second version must not leave the first version's tail behind:
    orphaned chunks stay in the index and keep answering questions."""
    long_args = _args(crop="Cotton")
    ingest.ingest_file(db_conn, doc, long_args)
    with db_conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM document_chunks WHERE source_id = "
                    "(SELECT id FROM sources WHERE organization = 'TEST ORG')")
        first_count = cur.fetchone()[0]
    assert first_count >= 2

    short = doc.parent / "cotton-guidance.md"
    short.write_text("A single short section about cotton nitrogen splitting "
                     "and the timing of the top dressing. " * 3, encoding="utf-8")

    ingest.ingest_file(db_conn, short, long_args)
    with db_conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM document_chunks WHERE source_id = "
                    "(SELECT id FROM sources WHERE organization = 'TEST ORG')")
        second_count = cur.fetchone()[0]

    assert second_count < first_count, "the previous version's extra chunks were not removed"


def test_unchanged_chunks_are_not_re_embedded(db_conn, doc, fake_embedder):
    args = _args(crop="Cotton")

    ingest.ingest_file(db_conn, doc, args)
    first_calls = list(fake_embedder)
    assert sum(first_calls) >= 2, "the first pass must embed everything"

    ingest.ingest_file(db_conn, doc, args)
    assert list(fake_embedder) == first_calls, (
        "identical text was re-embedded - the content_sha256 reuse path is broken"
    )

    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM document_chunks WHERE embedding IS NULL AND source_id = "
            "(SELECT id FROM sources WHERE organization = 'TEST ORG')",
        )
        assert cur.fetchone()[0] == 0, "reused vectors must be carried over, not dropped"


def test_write_without_an_embedding_provider_refuses(db_conn, doc, monkeypatch):
    """Writing un-embedded chunks would put text in the index that only
    metadata filtering can ever reach - a silently degraded corpus.

    Matches on the provider-agnostic wording: the default provider is local and
    needs no key at all, so the old "VOYAGE_API_KEY" message no longer applies.
    """
    monkeypatch.setattr(ingest.embeddings, "available", lambda: False)
    with pytest.raises(SystemExit, match="No embedding provider is available"):
        ingest.ingest_file(db_conn, doc, _args(crop="Cotton"))


def test_ingest_never_commits_the_callers_transaction(db_conn, doc, fake_embedder):
    """The regression that leaked test fixtures into the real corpus.

    `ingest_file` must leave the transaction open for the caller to commit or
    roll back. When it committed mid-way and wrote on a second connection, the
    suite started writing for real - and the leftover rows then made the
    un-embedded-chunk guard stop firing, because their hashes were already
    cached.
    """
    ingest.ingest_file(db_conn, doc, _args(crop="Cotton"))

    # Written and visible inside this transaction...
    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM document_chunks WHERE source_id = "
            "(SELECT id FROM sources WHERE organization = 'TEST ORG')",
        )
        assert cur.fetchone()[0] >= 2

    # ...but invisible to anyone else, because nothing was committed.
    import psycopg

    from app.config import DATABASE_URL

    with psycopg.connect(DATABASE_URL) as other, other.cursor() as cur:
        cur.execute("SELECT count(*) FROM sources WHERE organization = 'TEST ORG'")
        assert cur.fetchone()[0] == 0, "ingest_file committed - test data escaped into the real corpus"


def test_dry_run_touches_neither_the_database_nor_the_embedding_api(db_conn, doc, fake_embedder):
    with db_conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM document_chunks")
        before = cur.fetchone()[0]

    chunks, embedded, reused = ingest.ingest_file(db_conn, doc, _args(write=False, crop="Cotton"))

    assert chunks >= 2 and embedded == 0 and reused == 0
    assert fake_embedder == [], "a dry run must not spend embedding calls"
    with db_conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM document_chunks")
        assert cur.fetchone()[0] == before
