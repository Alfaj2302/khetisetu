from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BACKEND_DIR / ".env")

DATABASE_URL = os.environ.get("DATABASE_URL")
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8000"))
CORS_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(",")
    if origin.strip()
]

# Dev-only fallback so the app boots without a .env file; every real
# deployment must set its own SECRET_KEY via the environment.
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-insecure-secret-change-me")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))

# ---------------------------------------------------------------
# RAG
#
# Both halves are pluggable and both degrade instead of failing, because the
# corpus is ingested after the code ships and the default stack costs nothing.
#
#   EMBEDDING_PROVIDER=local  (default)  sentence-transformers on this machine
#                     =voyage            Voyage AI, needs VOYAGE_API_KEY
#
#   RAG_PROVIDER=groq  (default)  Llama 3.3 70B on Groq's free tier
#               =ollama           a local model, fully offline
#               =anthropic        Claude, the only one with native citations
#
# `GET /rag/status` reports which combination is live, so a weak answer is never
# mistaken for a missing credential.
# ---------------------------------------------------------------

# --- generation -------------------------------------------------

RAG_PROVIDER = os.environ.get("RAG_PROVIDER", "groq").strip().lower()

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY") or None
GROQ_API_KEY = os.environ.get("GROQ_API_KEY") or None

# Per-provider defaults. Groq and Ollama both speak the OpenAI wire format, so
# they share one client and differ only in base URL, model and key - which is
# also why OpenRouter or any other compatible endpoint works by setting
# RAG_BASE_URL without new code.
_GENERATION_DEFAULTS = {
    # Free tier, no card. Large enough for this task: read six paragraphs and
    # write 120 grounded words - no hard reasoning, which is where the gap to a
    # frontier model would actually show.
    #
    # Groq retires models without notice - llama-3.3-70b-versatile was the
    # obvious pick and 404s today. If this one goes the same way, list what the
    # key can actually reach rather than guessing:
    #   client.models.list()  (see rag/README.md)
    "groq": ("https://api.groq.com/openai/v1", "openai/gpt-oss-120b"),
    # Fully offline. Small model because a laptop without a GPU is the realistic
    # case; expect tens of seconds per answer.
    "ollama": ("http://localhost:11434/v1", "qwen2.5:3b"),
    "anthropic": (None, "claude-opus-5"),
}
_default_base, _default_model = _GENERATION_DEFAULTS.get(
    RAG_PROVIDER, _GENERATION_DEFAULTS["groq"],
)

RAG_BASE_URL = os.environ.get("RAG_BASE_URL") or _default_base
RAG_MODEL = os.environ.get("RAG_MODEL") or _default_model
RAG_MAX_TOKENS = int(os.environ.get("RAG_MAX_TOKENS", "2000"))
# Only Claude reads this; the OpenAI-compatible providers ignore it.
RAG_EFFORT = os.environ.get("RAG_EFFORT", "medium")

# Ollama serves the OpenAI API without auth but the client still requires some
# string, so give it one rather than making the user invent it.
RAG_API_KEY = (
    os.environ.get("RAG_API_KEY")
    or GROQ_API_KEY
    or ("ollama" if RAG_PROVIDER == "ollama" else None)
)

# --- embeddings -------------------------------------------------

EMBEDDING_PROVIDER = os.environ.get("EMBEDDING_PROVIDER", "local").strip().lower()
VOYAGE_API_KEY = os.environ.get("VOYAGE_API_KEY") or None

# bge-m3 is multilingual and 1024-dimensional, which matters twice over: the UI
# runs in English, Hindi and Marathi, and 1024 is already the width of
# document_chunks.embedding, so the default provider needs no migration.
_EMBEDDING_DEFAULTS = {
    "local": ("BAAI/bge-m3", 1024),
    "voyage": ("voyage-3.5", 1024),
}
_default_embed_model, _default_dim = _EMBEDDING_DEFAULTS.get(
    EMBEDDING_PROVIDER, _EMBEDDING_DEFAULTS["local"],
)

# EMBEDDING_DIM must match the model's real output width AND
# document_chunks.embedding - ingest refuses to run otherwise, because a
# mismatch surfaces as a Postgres error per row rather than one clear failure.
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL") or _default_embed_model
EMBEDDING_DIM = int(os.environ.get("EMBEDDING_DIM") or _default_dim)

# How many chunks reach the model. Small on purpose: every chunk is a document
# block in the request, and a wide context makes "only use these sources"
# harder to hold, not easier.
RAG_TOP_K = int(os.environ.get("RAG_TOP_K", "6"))

# Relevance cutoffs, in pgvector cosine distance (`<=>`: 0 identical, 1
# orthogonal, 2 opposite). Two of them, because one absolute number cannot do
# this job:
#
# RAG_MAX_DISTANCE is a loose sanity cap only. What counts as a "close" match is
# a property of the embedding model and the length of the texts, so a tight
# absolute threshold tuned against one model silently drops everything under
# another - and a retriever that returns nothing is indistinguishable from an
# un-ingested corpus. 0.9 rejects the actively unrelated without pretending to
# know where relevance ends.
#
# RAG_RELATIVE_MARGIN does the real filtering, and it is model-agnostic: keep
# only chunks within this distance of the best match for THIS query. Whatever
# scale the model works on, a chunk much worse than the best one is noise.
#
# Neither is the grounding guarantee. That is enforced on the response - Claude
# must cite a passage or the answer is discarded (see generation.py).
RAG_MAX_DISTANCE = float(os.environ.get("RAG_MAX_DISTANCE", "0.9"))
RAG_RELATIVE_MARGIN = float(os.environ.get("RAG_RELATIVE_MARGIN", "0.15"))

# Whether each half is live is asked via generation.available() /
# embeddings.available() rather than kept as a flag here - one source of truth,
# and tests can patch the single function instead of a module constant.
