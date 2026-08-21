-- 002: Give fertilizer_recommendations a source_id.
--
-- All 13 rows had source_id IS NULL, so GET /farmer/crop/{crop_id} and RAG
-- explain-mode could never populate their `sources` array — both always
-- returned []. The "Based on agricultural knowledge sources" panel had nothing
-- to render, and the citation plumbing was untestable.
--
-- sources.id 2 (ICAR) is the row the seed data already designates for this
-- table: "Intended source category for fertilizer_recommendations.csv - NOT
-- yet filled with a real document."
--
-- This does NOT make the guidance verified. is_verified stays FALSE, so the
-- API keeps returning its "Indicative only - not a verified agronomic
-- prescription" warning and RAG keeps setting used_placeholder_data = true.
-- The chain now honestly reads: placeholder dose -> placeholder ICAR citation.
-- Replace the sources row with a real document reference to make it real.
--
-- Idempotent: re-running matches no rows once source_id is set.

BEGIN;

UPDATE fertilizer_recommendations
SET source_id = (SELECT id FROM sources WHERE organization LIKE 'ICAR%' ORDER BY id LIMIT 1)
WHERE source_id IS NULL;

COMMIT;
