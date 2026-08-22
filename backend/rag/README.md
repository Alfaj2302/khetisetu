# RAG — the "why" behind the numbers

ML produces `Tomato: 46%`. A farmer reading `46%` learns nothing. This layer is
the **Why Tomato?** button: it finds the real agricultural documents about that
specific crop, hands them to a language model together with the figures ML
computed, and returns a plain-language explanation with its sources listed.

```
offline   rag/chunk.py                 paragraph-aware chunking, page offsets
          rag/ingest.py                read -> chunk -> embed -> document_chunks

request   app/services/crop_lexicon.py which crop is this question about?
          app/services/embeddings.py   text -> vector (local or Voyage)
          app/services/retrieval.py    metadata filter FIRST, then similarity
          app/services/generation.py   Groq / Ollama / Claude, with citations
          app/services/rag.py          orchestration + honest status reporting
```

Both halves are pluggable, and **the default stack costs nothing**:

| | default | alternatives |
|---|---|---|
| embeddings | `local` — sentence-transformers, `BAAI/bge-m3`, no key | `voyage` |
| generation | `groq` — Llama 3.3 70B, free tier | `ollama` (offline), `anthropic` |

Anthropic serves no embeddings endpoint, which is why the two halves are
separate providers at all. Groq and Ollama share one implementation because
both speak the OpenAI wire format — any other compatible endpoint (OpenRouter,
vLLM) works by setting `RAG_BASE_URL`, no code change.

**`bge-m3` is a quality choice, not only a free one.** The UI runs in English,
Hindi and Marathi. Measured against a real English bulletin: an English query
scores 0.35 cosine distance, the equivalent Marathi query 0.49 — both retrieve
the same correct passage. An English-only embedding model would not.

## The three rules, and where each is actually enforced

The rules are not prompt requests. Each one has a structural enforcement point
and a test that fails if it is removed.

### 1. Only say what's in the documents

Enforced on the **response**, not requested in the prompt. An answer that cites
nothing is discarded and replaced with the decline; `NO_GROUNDED_ANSWER`
short-circuits to the decline; and with no chunks retrieved, no backend is
called at all.

How a citation is *obtained* differs by backend, and this is the one place the
free stack is genuinely weaker:

**Claude** returns citations natively — each chunk goes in as a `document` block
with `citations: {"enabled": true}` and the API itself reports which passage
supports each sentence. A citation cannot point at text the model did not use.

**Every other backend** is asked for `[1]`-style markers plus a verbatim quote
per marker, and then **the quote is checked against the chunk it names**
(`quote_supported`): exact match after whitespace/case normalisation, falling
back to a 60% longest-contiguous-run ratio so a fixed typo still passes. A
fabricated quote fails and that citation is dropped; if none survive, the answer
is declined.

That is verification, not trust — it catches invention, which is the failure
that matters. It does *not* catch a model that quotes correctly and then reasons
badly around the quote, which native citations constrain more tightly. If this
ever serves real farmers acting on real advice, that gap is the reason to switch
`RAG_PROVIDER=anthropic`.

So "it made something up" is not a tuning problem here — it is a response the
code throws away. `GET /rag/status` reports `native_citations` so you always
know which of the two strengths is live.

### 2. Never mix crops

`retrieve()` filters on metadata **before** ranking by distance:

```
crop_id = <asked crop>  ->  admissible
crop_id IS NULL         ->  admissible (general agronomy)
crop_id = <other crop>  ->  never admissible
```

Filtering first is what makes this structural. Ranking first and filtering after
would mean an empty result whenever a crop's own documents aren't the nearest
neighbours — and the tempting fix for that is to relax the filter.

The rule is then **asserted a second time** in Python before anything is
returned (`assert_crop_isolation`). The SQL is assembled by string
concatenation, so an edit that drops the crop predicate would otherwise disable
the guarantee silently; instead it raises.

Ask mode had the real hole: it retrieved with `crop_id=None`, so a Cotton
question could be answered from Tomato chunks. `crop_lexicon` now recovers the
crop from the question text in English, Hindi and Marathi (`kapas`, `कापूस`,
`kanda`, `कांदा`). A question naming **two** crops is refused rather than
answered from one of them.

### 3. Flag unverified numbers

Every `fertilizer_recommendations` row is currently
`data_source = SYNTHETIC_PLACEHOLDER`, `is_verified = false`. Those figures are
injected inside an explicit `UNVERIFIED` block and the system prompt requires
any answer touching them to say so.

`used_placeholder_data` is computed from `is_verified` **in the database**, not
from whether the model remembered to include the warning — so the flag stays
correct even if the sentence is missing.

## Ingesting documents

Nothing is indexed yet. `GET /api/v1/rag/status` will say so:

```json
{ "chunks": 0, "readiness": "no corpus ingested" }
```

```bash
pip install -r requirements-rag.txt

# 1. Inspect the chunking. No API calls, no writes, costs nothing.
.venv/bin/python rag/ingest.py --file docs/icar-cotton.pdf --crop Cotton

# 2. Ingest for real.
.venv/bin/python rag/ingest.py --file docs/icar-cotton.pdf --crop Cotton \
    --organization ICAR --title "Cotton Production Technology" \
    --url https://icar.org.in/... --state Maharashtra --write

# 3. Or a whole folder, one sources row per file.
.venv/bin/python rag/ingest.py --dir docs/ --organization ICAR --write
```

**`--crop` is the flag to be careful about.** It is what rule 2 enforces
against. A Cotton bulletin ingested without `--crop` gets `crop_id NULL`, which
means "applies to every crop" — and the retriever cannot tell that apart from a
deliberate choice. Omit it only for genuinely crop-agnostic material (soil
testing, general nutrient theory). An unknown crop name is rejected rather than
silently treated as NULL.

Re-ingesting is safe and cheap: chunks are content-hashed, so unchanged text
keeps its existing vector and only new or edited text costs an embedding call.
A re-ingest replaces the source's chunks wholesale rather than upserting, since
a shorter second version would otherwise leave the first version's tail behind
as orphans that still answer queries.

Scanned PDFs are refused, not ingested empty — a source in the index that can
never support an answer is worse than a missing one.

## It degrades instead of breaking

The corpus arrives after the code, and the default embedding provider needs no
credential at all, so nothing here is required to boot:

| Situation | What happens |
|---|---|
| No generation key (`GROQ_API_KEY`) | Retrieved passages are quoted verbatim instead of explained. `generated_by: "extractive"`. |
| Generation backend unreachable (Ollama not running, Groq down) | Same extractive fallback — a `GenerationError` degrades rather than 500s. |
| Hosted embeddings selected without a key | Retrieval falls back to metadata-only filtering. `retrieval: "metadata"`. Ingest refuses to `--write`. |
| No documents ingested | Explain mode still answers from database columns — market rows and the computed score are real data that never needed a source. `generated_by: "template"`. Ask mode declines. |

`GET /rag/status` reports which combination is live, so a thin answer is
attributable to a missing key, an unreachable backend or an empty corpus rather
than looking like a bad model. Without it those causes are indistinguishable
from the outside.

**Startup cost.** The local model takes ~24s to load and ~2.7GB resident. The
API warms it in a daemon thread at startup so neither boot nor the first
"Why <crop>?" click pays for it; encoding a query afterwards is ~0.26s.
Ingesting ~3,000 chunks takes roughly 16 minutes on a CPU-only laptop.

## Configuration

```bash
# free default — only the Groq key, and it costs nothing
RAG_PROVIDER=groq                 # groq | ollama | anthropic
GROQ_API_KEY=gsk_...
EMBEDDING_PROVIDER=local          # local | voyage
EMBEDDING_MODEL=BAAI/bge-m3
EMBEDDING_DIM=1024

RAG_TOP_K=6
RAG_MAX_DISTANCE=0.9              # loose sanity cap
RAG_RELATIVE_MARGIN=0.15          # the cutoff that actually filters
```

Fully offline instead: `RAG_PROVIDER=ollama` (no key; expect tens of seconds per
answer without a GPU). Paid, strongest guarantee: `RAG_PROVIDER=anthropic` with
`ANTHROPIC_API_KEY`, which is the only backend with native citations.

`EMBEDDING_DIM`, the model's real `output_dimension`, and
`document_chunks.embedding`'s declared width must all be the same number.
Ingest checks and names whichever disagrees, because a mismatch otherwise
surfaces as a Postgres error per row rather than as one clear failure.

**Changing `EMBEDDING_MODEL` means re-embedding the whole corpus.** Vectors from
two models are not comparable, and mixing them returns plausible-looking wrong
neighbours rather than an error. `embedding_model` is stored per row and
filtered on at query time so the mistake is at least detectable.

## Design notes worth knowing

- **Relevance is judged relative to the best match, not against a fixed
  number.** A nearest neighbour always exists; that is not the same as it being
  relevant. But what counts as "close" is a property of the embedding model and
  of how long the texts are, so an absolute cosine ceiling tuned against one
  model drops everything under another — and it fails *silently*, looking
  exactly like a corpus nobody ingested. This bit during development: a 0.55
  ceiling rejected every correctly-ranked chunk. So `RAG_RELATIVE_MARGIN` keeps
  chunks within a margin of the best match for that query, and
  `RAG_MAX_DISTANCE` survives only as a loose guard against the actively
  unrelated. Neither is the grounding guarantee — that is the citation check on
  the response.

- **HNSW, not IVFFlat.** IVFFlat derives its centroids from the rows present
  when the index is built. Built on the empty table the schema creates — as it
  was — those centroids are meaningless and recall stays poor until someone
  reindexes by hand. HNSW needs no training pass and is correct from the first
  inserted row, which is what a corpus that starts empty and grows needs.

- **Queries and documents are embedded differently.** Voyage takes an
  `input_type`, and a question is not the same kind of text as a document
  paragraph. Using one code path for both is the most common way a working
  retriever quietly becomes a mediocre one, so the two are separate functions
  with no default.

- **Paragraph-aware chunking with sentence overlap.** A fixed character cut
  mid-sentence produces chunks whose embedding averages two unrelated topics.
  Overlap exists so a fact that straddles a boundary ("apply 40 kg/ha. This is
  split across two applications.") is complete in at least one chunk.

- **Prompt caching covers `[system + documents]`.** The "Why <crop>?" button
  sends different questions against the same retrieved set, so the breakpoint
  sits on the last document block and only the question varies after it.

- **Two kinds of grounding.** Explain mode's `template` answer is grounded in
  database columns; the `claude` answer is grounded in documents. Both are
  honest, and `generated_by` distinguishes them rather than blurring them into
  one confidence number.

## Tests

```bash
.venv/bin/pytest tests/test_rag_pipeline.py tests/test_rag_ingest.py -q
```

No network. The Claude path runs against a fake client, so the rules that matter
— decline when nothing is cited, decline on the sentinel, decline on a refusal,
map citations back to the right source, cache the right prefix — are tested
rather than assumed to start working once a key is present. The pgvector SQL,
the CHECK constraint and the embedding-reuse path all run against the real
database inside a rolled-back transaction.
