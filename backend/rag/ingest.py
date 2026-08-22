"""Ingest a document into `document_chunks`. The offline half of the RAG layer.

    read -> normalise -> chunk -> embed -> write

Run it once per document. Everything the retriever needs to enforce the crop
guardrail comes from the metadata you attach here, so attaching it correctly is
the whole job:

    --crop Cotton     this document may only answer Cotton questions
    (omitted)         general agronomy, admissible for any crop

That is the one flag worth being careful about. A Cotton bulletin ingested
without `--crop` becomes admissible for Tomato questions, and the retriever
cannot detect the mistake - to it, a NULL crop_id means "the ingester said this
applies generally".

Re-ingesting the same source is safe and cheap. Chunks are content-hashed, so
an unchanged chunk keeps its existing vector instead of being re-embedded, and
only changed or new text costs an API call.

Usage:
    # inspect the chunking without spending anything - no API calls at all
    .venv/bin/python rag/ingest.py --file docs/icar-cotton.pdf --crop Cotton

    # register a new source row and ingest against it
    .venv/bin/python rag/ingest.py --file docs/icar-cotton.pdf --crop Cotton \\
        --organization ICAR --title "Cotton Production Technology" \\
        --url https://icar.org.in/... --write

    # ingest against a source row that already exists
    .venv/bin/python rag/ingest.py --file docs/mpkv-onion.pdf --source-id 3 \\
        --crop Onion --state Maharashtra --season Kharif --write

    # everything in a folder, one source row per file
    .venv/bin/python rag/ingest.py --dir docs/ --organization ICAR --write
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

import psycopg  # noqa: E402

from app.config import DATABASE_URL, EMBEDDING_DIM, EMBEDDING_MODEL  # noqa: E402
from app.services import embeddings  # noqa: E402
from rag.chunk import Chunk, Page, chunk_pages, chunk_text  # noqa: E402

TEXT_SUFFIXES = {".txt", ".md", ".markdown"}
SUPPORTED = TEXT_SUFFIXES | {".pdf"}


# ---------------------------------------------------------------
# Reading
# ---------------------------------------------------------------


def read_pages(path: Path) -> list[Page]:
    if path.suffix.lower() in TEXT_SUFFIXES:
        return [Page(number=1, text=path.read_text(encoding="utf-8", errors="replace"))]
    if path.suffix.lower() == ".pdf":
        try:
            from pypdf import PdfReader
        except ModuleNotFoundError as exc:
            raise SystemExit(
                "PDF ingest needs pypdf - pip install -r requirements-rag.txt",
            ) from exc
        reader = PdfReader(str(path))
        pages = [Page(number=n, text=page.extract_text() or "") for n, page in enumerate(reader.pages, 1)]
        if not any(p.text.strip() for p in pages):
            raise SystemExit(
                f"{path.name}: no extractable text. This is a scanned PDF - it needs "
                f"OCR before it can be ingested, and ingesting it empty would put a "
                f"source in the index that can never support an answer.",
            )
        return pages
    raise SystemExit(f"{path.name}: unsupported type (expected {', '.join(sorted(SUPPORTED))})")


# ---------------------------------------------------------------
# Metadata resolution
# ---------------------------------------------------------------


def _lookup(cur: psycopg.Cursor, table: str, column: str, value: str | None) -> int | None:
    """Resolve a name to an id, or fail loudly.

    Never silently returns None for an unknown name: that would attach the
    document to "applies to everything" instead of to the thing you named, and
    for --crop that quietly disables the isolation guarantee.
    """
    if value is None:
        return None
    cur.execute(f"SELECT id FROM {table} WHERE lower({column}) = lower(%s)", (value,))
    row = cur.fetchone()
    if row is None:
        cur.execute(f"SELECT {column} FROM {table} ORDER BY id")
        known = ", ".join(r[0] for r in cur.fetchall())
        raise SystemExit(f"unknown {table[:-1]} {value!r}. Known values: {known}")
    return row[0]


def ensure_source(
    cur: psycopg.Cursor,
    *,
    source_id: int | None,
    organization: str | None,
    title: str | None,
    url: str | None,
    source_type: str,
) -> int:
    if source_id is not None:
        cur.execute("SELECT id FROM sources WHERE id = %s", (source_id,))
        if cur.fetchone() is None:
            raise SystemExit(f"source_id {source_id} does not exist in `sources`")
        return source_id

    # Reuse an identical row rather than accumulating duplicates across re-runs.
    cur.execute(
        "SELECT id FROM sources WHERE organization = %s AND title = %s",
        (organization, title),
    )
    row = cur.fetchone()
    if row is not None:
        return row[0]

    cur.execute(
        """
        INSERT INTO sources (organization, title, url, source_type, accessed_at)
        VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
        RETURNING id
        """,
        (organization, title, url, source_type),
    )
    return cur.fetchone()[0]


# ---------------------------------------------------------------
# Writing
# ---------------------------------------------------------------


def existing_vectors(cur: psycopg.Cursor, source_id: int) -> dict[str, str]:
    """content_sha256 -> pgvector literal, for chunks already embedded.

    This is what makes re-ingest cheap: unchanged text keeps its vector and
    costs nothing.
    """
    cur.execute(
        """
        SELECT content_sha256, embedding::text
        FROM document_chunks
        WHERE source_id = %s AND embedding IS NOT NULL
          AND content_sha256 IS NOT NULL AND embedding_model = %s
        """,
        (source_id, EMBEDDING_MODEL),
    )
    return {row[0]: row[1] for row in cur.fetchall()}


def write_chunks(
    cur: psycopg.Cursor,
    *,
    source_id: int,
    chunks: list[Chunk],
    vectors: list[str | None],
    crop_id: int | None,
    state_id: int | None,
    season_id: int | None,
    product_id: int | None,
) -> int:
    """Replace every chunk for this source, in one transaction.

    Delete-then-insert rather than upsert: a re-ingested document usually has a
    different number of chunks, and an upsert keyed on (source_id, chunk_index)
    would leave the tail of the previous, longer version behind as orphans that
    still answer queries.
    """
    cur.execute("DELETE FROM document_chunks WHERE source_id = %s", (source_id,))
    replaced = cur.rowcount
    cur.executemany(
        """
        INSERT INTO document_chunks (
            source_id, chunk_index, chunk_text, state_id, crop_id, season_id, product_id,
            embedding, embedding_model, page_start, page_end, char_start, char_end,
            token_count, content_sha256
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s::vector, %s, %s, %s, %s, %s, %s, %s)
        """,
        [
            (
                source_id, chunk.index, chunk.text, state_id, crop_id, season_id, product_id,
                vector, EMBEDDING_MODEL if vector else None,
                chunk.page_start, chunk.page_end, chunk.char_start, chunk.char_end,
                chunk.token_estimate, chunk.sha256,
            )
            for chunk, vector in zip(chunks, vectors, strict=True)
        ],
    )
    return replaced


# ---------------------------------------------------------------
# Driver
# ---------------------------------------------------------------


def ingest_file(
    conn: psycopg.Connection,
    path: Path,
    args: argparse.Namespace,
) -> tuple[int, int, int]:
    """Returns (chunks, newly_embedded, reused_vectors).

    Everything runs in the CALLER's transaction on the CALLER's connection, and
    this function never commits: `main()` commits once at the end, and tests roll
    back. That property is load-bearing, and an earlier version broke it by
    committing mid-way and opening a second connection for the write. Two things
    followed, both worth recording:

    * the test suite started writing to the real database instead of rolling
      back, leaving test fixtures in `document_chunks` that real questions then
      retrieved as though they were a genuine ICAR document;
    * because those rows persisted between tests, the "refuse to write
      un-embedded chunks" guard stopped firing - its chunks were already cached,
      so `needed` was empty - and a document was written with no vectors at all.

    The concern behind that change is real: embedding a large document can leave
    this connection idle-in-transaction for many minutes, and a tunnelled
    connection may be dropped meanwhile. That belongs at the connection level -
    see the keepalive settings in `main()` - not in writing outside the caller's
    transaction.
    """
    chunks = chunk_pages(read_pages(path))
    if not chunks:
        print(f"  {path.name}: no usable text after normalisation - skipped")
        return (0, 0, 0)

    with conn.cursor() as cur:
        crop_id = _lookup(cur, "crops", "name", args.crop)
        state_id = _lookup(cur, "states", "name", args.state)
        season_id = _lookup(cur, "seasons", "name", args.season)
        product_id = _lookup(cur, "products", "product_name", args.product)

        pages = {c.page_start for c in chunks if c.page_start}
        scope = args.crop or "ALL CROPS (crop_id NULL)"
        print(f"  {path.name}: {len(chunks)} chunks over {len(pages) or 1} page(s) -> crop: {scope}")

        if not args.write:
            longest = max(chunks, key=lambda c: len(c.text))
            print(f"    median size ~{sorted(len(c.text) for c in chunks)[len(chunks) // 2]} chars, "
                  f"longest {len(longest.text)}")
            print(f"    first chunk: {chunks[0].text[:160].strip()}...")
            return (len(chunks), 0, 0)

        source_id = ensure_source(
            cur,
            source_id=args.source_id,
            organization=args.organization,
            title=args.title or path.stem.replace("-", " ").replace("_", " ").title(),
            url=args.url,
            source_type=args.source_type,
        )

        cached = existing_vectors(cur, source_id)
        needed = [c for c in chunks if c.sha256 not in cached]
        fresh: dict[str, str] = {}
        if needed:
            # Checked before writing anything: chunks stored without a vector can
            # only ever be reached by metadata filtering, never by semantic
            # search, which is a silently degraded corpus rather than an error.
            if not embeddings.available():
                raise SystemExit(
                    "No embedding provider is available. Ingest without embeddings "
                    "would write chunks that only metadata filtering can ever "
                    "reach - configure EMBEDDING_PROVIDER, or drop --write to "
                    "inspect the chunking first.",
                )
            print(f"    embedding {len(needed)} chunk(s) with {EMBEDDING_MODEL} "
                  f"({EMBEDDING_DIM}d); reusing {len(chunks) - len(needed)}")
            vectors = embeddings.embed_documents([c.text for c in needed])
            fresh = {c.sha256: embeddings.to_pgvector(v) for c, v in zip(needed, vectors, strict=True)}

        ordered = [fresh.get(c.sha256) or cached.get(c.sha256) for c in chunks]
        replaced = write_chunks(
            cur, source_id=source_id, chunks=chunks, vectors=ordered,
            crop_id=crop_id, state_id=state_id, season_id=season_id, product_id=product_id,
        )
        print(f"    wrote {len(chunks)} chunks as source_id={source_id} (replaced {replaced})")
        return (len(chunks), len(needed), len(chunks) - len(needed))


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    target = ap.add_mutually_exclusive_group(required=True)
    target.add_argument("--file", type=Path, help="one document (.pdf, .txt, .md)")
    target.add_argument("--dir", type=Path, help="every supported document in this folder")

    ap.add_argument("--crop", help="restrict this document to one crop, by crops.name. "
                                   "OMIT ONLY for genuinely crop-agnostic material.")
    ap.add_argument("--state", help="states.name")
    ap.add_argument("--season", help="seasons.name (Kharif, Rabi, Zaid)")
    ap.add_argument("--product", help="products.product_name")

    ap.add_argument("--source-id", type=int, help="ingest against an existing sources row")
    ap.add_argument("--organization", help="e.g. ICAR, MPKV (used when creating a sources row)")
    ap.add_argument("--title", help="defaults to the filename")
    ap.add_argument("--url")
    ap.add_argument("--source-type", default="RESEARCH_PUBLICATION")

    ap.add_argument("--write", action="store_true",
                    help="actually embed and write (default: show the chunk plan, spend nothing)")
    args = ap.parse_args()

    if not DATABASE_URL:
        print("DATABASE_URL is not set (backend/.env)", file=sys.stderr)
        return 1

    if args.dir:
        paths = sorted(p for p in args.dir.iterdir() if p.suffix.lower() in SUPPORTED)
        if not paths:
            print(f"no {'/'.join(sorted(SUPPORTED))} files in {args.dir}", file=sys.stderr)
            return 1
        if args.source_id:
            raise SystemExit("--source-id is single-document only; --dir creates one source per file")
    else:
        paths = [args.file]
        if not args.file.exists():
            print(f"{args.file} does not exist", file=sys.stderr)
            return 1

    if args.write and not (args.source_id or args.organization):
        raise SystemExit("--write needs either --source-id or --organization to attribute the source")

    print(f"{'INGEST' if args.write else 'DRY RUN'}: {len(paths)} document(s)\n")
    totals = [0, 0, 0]
    # TCP keepalives, because this connection sits idle-in-transaction for the
    # whole embedding pass - minutes for a large document on a CPU-only machine.
    # DATABASE_URL points through an ngrok tunnel, and tunnels, SSH forwards and
    # cloud load balancers all drop silent connections; without keepalives the
    # drop only surfaces at the final write, after the expensive work is done.
    # This is the right layer for that problem: the alternative, committing
    # mid-way and writing on a second connection, takes the writes outside the
    # caller's transaction and stops tests being able to roll back.
    with psycopg.connect(
        DATABASE_URL,
        keepalives=1,
        keepalives_idle=30,
        keepalives_interval=10,
        keepalives_count=5,
    ) as conn:
        for path in paths:
            counts = ingest_file(conn, path, args)
            totals = [a + b for a, b in zip(totals, counts, strict=True)]
        if args.write:
            conn.commit()

    print(f"\n{totals[0]} chunks total | {totals[1]} embedded | {totals[2]} vectors reused")
    if not args.write:
        print("DRY RUN - nothing written, no embedding API calls made. Re-run with --write.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
