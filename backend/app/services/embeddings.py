"""Text -> vectors, for the retrieval half of RAG.

Two providers, selected by `EMBEDDING_PROVIDER`:

    local   sentence-transformers on this machine. No key, no per-token cost,
            works offline. The default.
    voyage  Voyage AI. A network call and a key, kept because it is the
            managed option if the local model ever becomes inconvenient.

The default is `local` with **BAAI/bge-m3**, and that is a quality decision as
much as a cost one: the farmer-facing UI runs in English, Hindi and Marathi, and
a farmer typing "कापूस साठी खत किती?" needs a model that embeds Devanagari into
the same space as the English bulletins it must match. bge-m3 is multilingual
and 1024-dimensional, which is already the width of `document_chunks.embedding`.

Two things this module exists to get right:

* **Asymmetric embedding.** A question and a document paragraph are different
  kinds of text, and most retrieval models want to be told which they are
  given - Voyage via `input_type`, most sentence-transformers models via a
  prefix ("query: " / "passage: "). Using one code path for both is the most
  common way a working retriever quietly becomes a mediocre one, so the two are
  separate functions with no default, and the prefixes are per-model because
  applying the wrong one is worse than applying none.

* **Dimension agreement.** `EMBEDDING_DIM`, the model's real output width and
  the database column must be the same number. Checked up front, because
  otherwise Postgres rejects each row individually and the error names neither
  the model nor the expected size.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from ..config import (
    EMBEDDING_DIM,
    EMBEDDING_MODEL,
    EMBEDDING_PROVIDER,
    VOYAGE_API_KEY,
)

InputType = Literal["query", "document"]

# Voyage caps a single request; batching above this is the caller's job.
MAX_BATCH = 128

# Instruction prefixes expected by local models, keyed by model name.
#
# These are not interchangeable and not optional. The e5 family was trained with
# "query: " / "passage: " on every input and loses accuracy without them;
# bge-*-v1.5 wants an instruction on the query side only; bge-m3 was trained
# without any prefix and gets *worse* if one is bolted on. Hence a table rather
# than a global default - an unknown model gets no prefix, which is the safe
# assumption.
LOCAL_PREFIXES: dict[str, tuple[str, str]] = {
    # model name: (query prefix, document prefix)
    "BAAI/bge-m3": ("", ""),
    "intfloat/multilingual-e5-large": ("query: ", "passage: "),
    "intfloat/multilingual-e5-base": ("query: ", "passage: "),
    "intfloat/multilingual-e5-small": ("query: ", "passage: "),
    "BAAI/bge-large-en-v1.5": (
        "Represent this sentence for searching relevant passages: ", "",
    ),
    "BAAI/bge-base-en-v1.5": (
        "Represent this sentence for searching relevant passages: ", "",
    ),
}


class EmbeddingError(RuntimeError):
    """Embedding was attempted but could not be completed."""


def available() -> bool:
    """Whether embeddings can be produced at all.

    The local provider needs no credential, so the default configuration is
    always available - retrieval only degrades to metadata-only filtering if
    someone explicitly selects a hosted provider without its key.
    """
    if EMBEDDING_PROVIDER == "voyage":
        return VOYAGE_API_KEY is not None
    return True


def describe() -> str:
    """Human-readable provider/model, for GET /rag/status."""
    return f"{EMBEDDING_PROVIDER}:{EMBEDDING_MODEL}"


# ---------------------------------------------------------------
# local (sentence-transformers)
# ---------------------------------------------------------------


@lru_cache(maxsize=1)
def _local_model():
    """Load once per process.

    First call downloads the weights (~2.3GB for bge-m3) and takes a while;
    every call after is in-memory. Cached rather than reloaded because loading
    is far more expensive than encoding.
    """
    try:
        from sentence_transformers import SentenceTransformer
    except ModuleNotFoundError as exc:  # pragma: no cover - dependency guard
        raise EmbeddingError(
            "the `sentence-transformers` package is not installed - "
            "pip install -r requirements.txt",
        ) from exc
    return SentenceTransformer(EMBEDDING_MODEL, device="cpu")


def warm_up() -> None:
    """Load the local model now rather than on someone's first question.

    Measured on a CPU-only laptop, bge-m3 takes ~24s to load from cache and
    ~0.26s to encode a query. Without this the first "Why <crop>?" click after a
    restart pays the 24s, which reads as a hung page. Called from a background
    thread at startup so boot is not blocked either.

    Safe to call when the provider is hosted or the package is missing - warming
    is an optimisation, and a failure here must not stop the API serving.
    """
    if EMBEDDING_PROVIDER != "local":
        return
    try:
        _local_model()
    except Exception:  # noqa: BLE001 - never let a warm-up failure break boot
        pass


def _local_embed(texts: list[str], input_type: InputType) -> list[list[float]]:
    query_prefix, doc_prefix = LOCAL_PREFIXES.get(EMBEDDING_MODEL, ("", ""))
    prefix = query_prefix if input_type == "query" else doc_prefix
    prepared = [f"{prefix}{text}" for text in texts]

    # normalize_embeddings makes every vector unit length, which is what makes
    # pgvector's cosine distance operator meaningful and comparable across rows.
    vectors = _local_model().encode(
        prepared, normalize_embeddings=True, show_progress_bar=False,
    )
    return [[float(x) for x in vector] for vector in vectors]


# ---------------------------------------------------------------
# voyage
# ---------------------------------------------------------------


@lru_cache(maxsize=1)
def _voyage_client():
    if VOYAGE_API_KEY is None:
        raise EmbeddingError(
            "EMBEDDING_PROVIDER=voyage but VOYAGE_API_KEY is not set. Either set "
            "the key or switch to EMBEDDING_PROVIDER=local, which needs neither.",
        )
    try:
        import voyageai
    except ModuleNotFoundError as exc:  # pragma: no cover - dependency guard
        raise EmbeddingError("the `voyageai` package is not installed") from exc
    return voyageai.Client(api_key=VOYAGE_API_KEY)


def _voyage_embed(texts: list[str], input_type: InputType) -> list[list[float]]:
    result = _voyage_client().embed(
        texts,
        model=EMBEDDING_MODEL,
        input_type=input_type,
        output_dimension=EMBEDDING_DIM,
    )
    return [[float(x) for x in vector] for vector in result.embeddings]


# ---------------------------------------------------------------
# dispatch
# ---------------------------------------------------------------


def _embed(texts: list[str], input_type: InputType) -> list[list[float]]:
    if not texts:
        return []
    if len(texts) > MAX_BATCH:
        raise EmbeddingError(f"batch of {len(texts)} exceeds the {MAX_BATCH} limit")

    vectors = (
        _voyage_embed(texts, input_type)
        if EMBEDDING_PROVIDER == "voyage"
        else _local_embed(texts, input_type)
    )

    # Fail on the response rather than per-row inside the insert: a model whose
    # real width differs from EMBEDDING_DIM produces vectors Postgres rejects
    # one at a time, with an error naming neither the model nor the expectation.
    for vector in vectors:
        if len(vector) != EMBEDDING_DIM:
            raise EmbeddingError(
                f"{EMBEDDING_MODEL} returned {len(vector)}-dim vectors but "
                f"EMBEDDING_DIM is {EMBEDDING_DIM}. Set EMBEDDING_DIM to the "
                f"model's real width AND migrate document_chunks.embedding to "
                f"match - all three must agree.",
            )
    return vectors


def embed_query(text: str) -> list[float]:
    """Embed a user question. The input type is not cosmetic - see above."""
    return _embed([text], "query")[0]


def embed_documents(texts: list[str]) -> list[list[float]]:
    """Embed corpus chunks, in batches of at most MAX_BATCH."""
    out: list[list[float]] = []
    for start in range(0, len(texts), MAX_BATCH):
        out.extend(_embed(texts[start : start + MAX_BATCH], "document"))
    return out


def to_pgvector(vector: list[float]) -> str:
    """pgvector's text input format.

    psycopg has no adapter for VECTOR, and a Python list becomes an array
    literal, which Postgres rejects. Casting `%s::vector` over this string is
    the documented route.
    """
    return "[" + ",".join(repr(float(x)) for x in vector) + "]"
