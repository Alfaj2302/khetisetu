-- Make document_chunks actually usable by the RAG layer.
--
-- Four things, all of which the original "pgvector / Vector DB" box left open:
--
-- 1. DIMENSION. schema.sql declared VECTOR(1536) for "whatever embedding model
--    Phase 2 picks"; the live database had drifted to VECTOR(768). Phase 2
--    picked voyage-3.5 at output_dimension 1024, so both are reconciled to
--    1024 here. Safe as a plain ALTER because the table is empty - if you are
--    running this against a populated corpus, TRUNCATE first: vectors from a
--    different model are not comparable to voyage-3.5 vectors, and mixing them
--    silently returns nonsense neighbours rather than an error.
--
-- 2. embedding_model. Which model produced the vector. Without it, a model
--    switch is undetectable after the fact and the index quietly mixes two
--    incompatible spaces. Retrieval filters on it.
--
-- 3. Citation provenance (page_start / page_end / char_start / char_end).
--    "Only say what's in the documents" is only checkable if a claim can be
--    traced back to a location, not just to an organisation name.
--
-- 4. HNSW instead of IVFFlat. IVFFlat derives its centroids from the data
--    present when the index is built - built on an empty table, as it was, the
--    centroids are meaningless and recall stays bad until it is reindexed by
--    hand. HNSW needs no training pass, so it is correct from the first row,
--    which is what a corpus that starts empty and grows needs.

ALTER TABLE document_chunks
    ALTER COLUMN embedding TYPE VECTOR(1024);

ALTER TABLE document_chunks
    ADD COLUMN IF NOT EXISTS embedding_model  VARCHAR(100),
    ADD COLUMN IF NOT EXISTS page_start       INT,
    ADD COLUMN IF NOT EXISTS page_end         INT,
    ADD COLUMN IF NOT EXISTS char_start       INT,
    ADD COLUMN IF NOT EXISTS char_end         INT,
    ADD COLUMN IF NOT EXISTS token_count      INT,
    -- Lets re-ingesting the same document be idempotent without re-embedding
    -- unchanged chunks, and makes an accidental double-ingest detectable.
    ADD COLUMN IF NOT EXISTS content_sha256   CHAR(64);

-- An embedded row must say which model embedded it. Enforced rather than
-- documented, because the failure mode (two vector spaces in one index) is
-- invisible at query time.
ALTER TABLE document_chunks
    DROP CONSTRAINT IF EXISTS chunk_embedding_has_model;
ALTER TABLE document_chunks
    ADD CONSTRAINT chunk_embedding_has_model
    CHECK (embedding IS NULL OR embedding_model IS NOT NULL);

DROP INDEX IF EXISTS idx_chunks_embedding;
CREATE INDEX idx_chunks_embedding ON document_chunks
    USING hnsw (embedding vector_cosine_ops);

-- Retrieval filters on metadata FIRST and only then ranks by distance, so the
-- metadata index carries crop_id leading: the crop filter is the one that must
-- never be skipped (a Cotton answer built from Tomato chunks is the failure
-- this whole layer exists to prevent).
DROP INDEX IF EXISTS idx_chunks_metadata;
CREATE INDEX idx_chunks_metadata ON document_chunks (crop_id, state_id, season_id);

-- Cheap guard for the "has this source been ingested yet" check.
CREATE INDEX IF NOT EXISTS idx_chunks_source ON document_chunks (source_id);
