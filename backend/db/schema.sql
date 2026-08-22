-- =====================================================================
-- FasalCast / KhetiSetu — PostgreSQL schema
-- Matches the 14 CSVs already delivered (columns line up 1:1 for COPY/
-- pandas.to_sql loading) plus 3 additions this design adds on top:
--   district_aliases   - the district-name crosswalk flagged in the data audit
--   document_chunks     - pgvector storage for the RAG layer (not in the original spec)
--   auth columns on users, is_verified on fertilizer_recommendations
-- Tables are ordered so every foreign key references a table already
-- created above it - this file runs top to bottom with no reordering.
-- =====================================================================

CREATE EXTENSION IF NOT EXISTS vector;

-- ---------------------------------------------------------------
-- REFERENCE TABLES
-- ---------------------------------------------------------------

CREATE TABLE states (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(100) NOT NULL UNIQUE,
    state_code  VARCHAR(10)
);

CREATE TABLE districts (
    id              SERIAL PRIMARY KEY,
    state_id        INT NOT NULL REFERENCES states(id),
    name            VARCHAR(100) NOT NULL,
    latitude        NUMERIC(8,4),
    longitude       NUMERIC(8,4),
    also_known_as   VARCHAR(100),  -- quick-glance alternate name, e.g. 'Aurangabad' for Chhatrapati Sambhajinagar
    UNIQUE (state_id, name)
);

-- The crosswalk: every spelling variant of a district seen in any source
-- file maps back to one canonical district_id. This is what the ETL
-- join logic uses instead of fuzzy-matching text every time.
CREATE TABLE district_aliases (
    id              SERIAL PRIMARY KEY,
    district_id     INT NOT NULL REFERENCES districts(id),
    alias_name      VARCHAR(100) NOT NULL,
    seen_in_source  VARCHAR(150),  -- e.g. 'Sales_Bio.csv', 'ICRISAT-District_Level_Data.csv'
    UNIQUE (alias_name, seen_in_source)
);

CREATE TABLE crops (
    id               SERIAL PRIMARY KEY,
    name             VARCHAR(100) NOT NULL UNIQUE,
    scientific_name  VARCHAR(150),
    crop_category    VARCHAR(100)
);

CREATE TABLE seasons (
    id           SERIAL PRIMARY KEY,
    name         VARCHAR(50) NOT NULL UNIQUE,
    start_month  INT CHECK (start_month BETWEEN 1 AND 12),
    end_month    INT CHECK (end_month BETWEEN 1 AND 12)
);

-- NOTE: the original spec's products table had a free-text 'crop' column.
-- Dropped here on purpose - one product maps to MANY crops (Prerak has
-- Chickpea/Cotton/Wheat/Soybean/Rice variants), so that relationship
-- belongs in crop_calendar's (product_id, crop_id) pair, not as a single
-- text field that can only ever name one crop.
CREATE TABLE products (
    id               SERIAL PRIMARY KEY,
    product_name     VARCHAR(150) NOT NULL UNIQUE,
    product_type     VARCHAR(100),
    fertilizer_type  VARCHAR(50),
    shelf_life_days  INT,
    data_source      VARCHAR(20) NOT NULL DEFAULT 'ACTUAL' CHECK (data_source IN ('ACTUAL','SYNTHETIC')),
    notes            TEXT
);

-- ---------------------------------------------------------------
-- USERS  (auth columns added - the original spec's users table had
-- no credentials, but /auth/login and /auth/register need something
-- to check against)
-- ---------------------------------------------------------------

CREATE TABLE users (
    id             BIGSERIAL PRIMARY KEY,
    name           VARCHAR(150),
    role           VARCHAR(20) NOT NULL CHECK (role IN ('FARMER','AGRI_BUSINESS','ADMIN')),
    email          VARCHAR(150) UNIQUE,
    password_hash  TEXT,
    state_id       INT REFERENCES states(id),
    district_id    INT REFERENCES districts(id),
    phone          VARCHAR(30),
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE sources (
    id                SERIAL PRIMARY KEY,
    organization      VARCHAR(200),
    title             TEXT,
    source_type       VARCHAR(100),
    url               TEXT,
    publication_date  DATE,
    accessed_at       TIMESTAMP,
    notes             TEXT
);

-- ---------------------------------------------------------------
-- CORE DOMAIN TABLES
-- ---------------------------------------------------------------

-- The rulebook. product_id is NULLABLE: a row with product_id NULL means
-- "this crop is grown here this month" (what's actually populated today,
-- reshaped from Crop_product.csv); a row with product_id set means "this
-- specific product is typically used on this crop this month" (the
-- original spec's intent - not yet populated, ready for when you add it).
CREATE TABLE crop_calendar (
    id              SERIAL PRIMARY KEY,
    state_id        INT NOT NULL REFERENCES states(id),
    district_id     INT NOT NULL REFERENCES districts(id),
    crop_id         INT NOT NULL REFERENCES crops(id),
    product_id      INT REFERENCES products(id),
    season_id       INT NOT NULL REFERENCES seasons(id),
    month           INT NOT NULL CHECK (month BETWEEN 1 AND 12),
    expected_usage  BOOLEAN NOT NULL DEFAULT TRUE,
    usage_weight    NUMERIC(4,3) DEFAULT 1.0,
    source          TEXT,
    UNIQUE (district_id, crop_id, product_id, month)
);
CREATE INDEX idx_crop_calendar_lookup ON crop_calendar (district_id, month);

-- Your real Sales_Bio.csv transactions (data_source='ACTUAL') plus the
-- 10-year synthetic backward extension (data_source='SYNTHETIC').
CREATE TABLE historical_sales (
    id                     BIGSERIAL PRIMARY KEY,
    district_id            INT NOT NULL REFERENCES districts(id),
    product_id             INT NOT NULL REFERENCES products(id),
    crop_id                INT REFERENCES crops(id),  -- nullable: UNRESOLVED rows genuinely have no assigned crop
    crop_source            VARCHAR(40) CHECK (crop_source IN
                              ('EXPLICIT','INFERRED_FROM_CALENDAR','INFERRED_FROM_CALENDAR_SYNTHETIC','UNRESOLVED')),
    fiscal_year            VARCHAR(10) NOT NULL,   -- e.g. '2020-21', kept as-is from source
    year_start             INT NOT NULL,           -- e.g. 2020 - plain int for joining to calendar-year tables
    month                  INT NOT NULL CHECK (month BETWEEN 1 AND 12),
    qty_in_pkts            NUMERIC,
    qty_in_sku             NUMERIC,
    gross_amount           NUMERIC,
    acre_coverage          NUMERIC,
    material_sku           VARCHAR(30),
    material_description   TEXT,
    category               VARCHAR(50),
    form                   VARCHAR(20),
    data_source            VARCHAR(20) NOT NULL CHECK (data_source IN ('ACTUAL','SYNTHETIC')),
    created_at             TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
-- This is the exact join the ML feature pipeline and Flow A scoring both run constantly
CREATE INDEX idx_sales_feature_lookup ON historical_sales (district_id, crop_id, product_id, year_start, month);
CREATE INDEX idx_sales_data_source ON historical_sales (data_source);

-- Reshaped ICRISAT (data_source='ACTUAL' for 2016-17) extended to 2025
-- and to Tomato/Chilli/Grapes, which had no ICRISAT column at all.
CREATE TABLE crop_production (
    id                    BIGSERIAL PRIMARY KEY,
    district_id           INT NOT NULL REFERENCES districts(id),
    crop_id               INT NOT NULL REFERENCES crops(id),
    year                  INT NOT NULL,
    area_1000ha           NUMERIC,
    production_1000tons   NUMERIC,
    yield_kg_per_ha       NUMERIC,
    data_source           VARCHAR(20) NOT NULL CHECK (data_source IN ('ACTUAL','SYNTHETIC')),
    source                TEXT,
    UNIQUE (district_id, crop_id, year)
);
CREATE INDEX idx_crop_production_lookup ON crop_production (district_id, crop_id, year);

-- The table that was missing entirely from the original 3 uploads: crop
-- PRODUCE demand vs supply (not fertilizer demand - that's historical_sales).
-- demand_gap is GENERATED so it can never drift out of sync with the two
-- numbers it's computed from.
CREATE TABLE crop_market_data (
    id                    BIGSERIAL PRIMARY KEY,
    district_id           INT NOT NULL REFERENCES districts(id),
    crop_id               INT NOT NULL REFERENCES crops(id),
    year                  INT NOT NULL,
    expected_supply_qty   NUMERIC,
    expected_demand_qty   NUMERIC,
    demand_gap            NUMERIC GENERATED ALWAYS AS (expected_demand_qty - expected_supply_qty) STORED,
    unit                  VARCHAR(20) DEFAULT 'quintal',
    supply_data_source    VARCHAR(20) CHECK (supply_data_source IN ('ACTUAL','SYNTHETIC')),
    demand_data_source    VARCHAR(20) CHECK (demand_data_source IN ('ACTUAL','SYNTHETIC')),
    demand_source_notes  TEXT,
    UNIQUE (district_id, crop_id, year)
);
CREATE INDEX idx_crop_market_lookup ON crop_market_data (district_id, crop_id, year);

CREATE TABLE weather_history (
    id             BIGSERIAL PRIMARY KEY,
    district_id    INT NOT NULL REFERENCES districts(id),
    year           INT NOT NULL,
    month          INT NOT NULL CHECK (month BETWEEN 1 AND 12),
    rainfall_mm    NUMERIC,
    temperature_c  NUMERIC,
    humidity_pct   NUMERIC,
    source         TEXT,
    UNIQUE (district_id, year, month)
);
CREATE INDEX idx_weather_history_lookup ON weather_history (district_id, year, month);

-- Live/forecast weather is conceptually different from history (spec's
-- own distinction) - short retention, refreshed from an API, never
-- backfilled with 10 years of synthetic data the way weather_history was.
CREATE TABLE weather_forecast (
    id             BIGSERIAL PRIMARY KEY,
    district_id    INT NOT NULL REFERENCES districts(id),
    forecast_date  DATE NOT NULL,
    rainfall_mm    NUMERIC,
    temperature_c  NUMERIC,
    humidity_pct   NUMERIC,
    source         VARCHAR(100),
    retrieved_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (district_id, forecast_date)
);

CREATE TABLE inventory (
    id                   BIGSERIAL PRIMARY KEY,
    district_id          INT NOT NULL REFERENCES districts(id),
    product_id           INT NOT NULL REFERENCES products(id),
    quantity             NUMERIC,
    batch_no             VARCHAR(100),
    manufacturing_date   DATE,
    expiry_date          DATE,
    updated_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    data_source          VARCHAR(20) NOT NULL DEFAULT 'SYNTHETIC' CHECK (data_source IN ('ACTUAL','SYNTHETIC')),
    notes                TEXT
);
CREATE INDEX idx_inventory_lookup ON inventory (district_id, product_id);

-- previous_crop_id and sowing_month are the 2 columns the live /farmer
-- form actually collects that the original spec's table didn't have.
-- user_id is nullable and OPTIONAL: it lets a logged-in farmer see/edit
-- their own past submissions. The anonymization rule is enforced by
-- never selecting user_id in the Business-side aggregation query, not
-- by omitting the column here.
CREATE TABLE farmer_crop_intent (
    id                     BIGSERIAL PRIMARY KEY,
    user_id                BIGINT REFERENCES users(id),
    district_id            INT NOT NULL REFERENCES districts(id),
    crop_id                INT NOT NULL REFERENCES crops(id),
    previous_crop_id       INT REFERENCES crops(id),
    season_id              INT NOT NULL REFERENCES seasons(id),
    year                   INT NOT NULL,
    sowing_month           INT CHECK (sowing_month BETWEEN 1 AND 12),
    land_area_acres        NUMERIC,
    irrigation_available   BOOLEAN,
    soil_type              VARCHAR(100),
    created_at             TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    data_source            VARCHAR(20) NOT NULL DEFAULT 'ACTUAL' CHECK (data_source IN ('ACTUAL','SYNTHETIC')),
    notes                  TEXT
);
-- The exact query the Business dashboard's "Farmer crop intent" chart runs:
-- GROUP BY district_id, crop_id - never SELECT user_id alongside it.
CREATE INDEX idx_intent_aggregation ON farmer_crop_intent (district_id, crop_id, season_id, year);

-- is_verified defaults FALSE on purpose: every row is a placeholder until
-- a human checks it against a real ICAR/university document and flips it.
-- The API should refuse to serve is_verified=FALSE rows to a real farmer
-- in production - see the RAG guardrails discussion from the dev plan.
CREATE TABLE fertilizer_recommendations (
    id                    BIGSERIAL PRIMARY KEY,
    state_id              INT REFERENCES states(id),
    district_id           INT REFERENCES districts(id),
    crop_id               INT NOT NULL REFERENCES crops(id),
    season_id             INT REFERENCES seasons(id),
    product_id            INT REFERENCES products(id),
    soil_type             VARCHAR(100),
    nitrogen_kg_ha        NUMERIC,
    phosphorus_kg_ha      NUMERIC,
    potassium_kg_ha       NUMERIC,
    application_stage     VARCHAR(200),
    recommendation_text   TEXT,
    source_id             INT REFERENCES sources(id),
    is_verified           BOOLEAN NOT NULL DEFAULT FALSE,
    data_source           VARCHAR(30) NOT NULL DEFAULT 'SYNTHETIC_PLACEHOLDER'
);

-- ---------------------------------------------------------------
-- OUTPUT TABLES  (written by the batch ML job, read by the API - never
-- computed live for the Business dashboard)
-- ---------------------------------------------------------------

CREATE TABLE forecast (
    id                BIGSERIAL PRIMARY KEY,
    district_id       INT NOT NULL REFERENCES districts(id),
    product_id        INT NOT NULL REFERENCES products(id),
    crop_id           INT REFERENCES crops(id),
    year              INT NOT NULL,
    month             INT NOT NULL CHECK (month BETWEEN 1 AND 12),
    predicted_demand  NUMERIC NOT NULL,
    lower_bound       NUMERIC,
    upper_bound       NUMERIC,
    confidence        VARCHAR(30),
    model_version     VARCHAR(50) NOT NULL,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CHECK (lower_bound IS NULL OR upper_bound IS NULL OR lower_bound <= predicted_demand),
    CHECK (upper_bound IS NULL OR lower_bound IS NULL OR predicted_demand <= upper_bound),
    UNIQUE (district_id, product_id, crop_id, year, month, model_version)
);

CREATE TABLE recommendations (
    id                     BIGSERIAL PRIMARY KEY,
    district_id            INT NOT NULL REFERENCES districts(id),
    product_id             INT NOT NULL REFERENCES products(id),
    forecast_quantity      NUMERIC,
    current_stock          NUMERIC,
    safety_stock           NUMERIC,
    recommended_dispatch   NUMERIC,
    action                 VARCHAR(30) CHECK (action IN
                             ('DISPATCH','HOLD','TRANSFER','MANUFACTURE','REDUCE_PRODUCTION','MONITOR')),
    reason                 TEXT,
    created_at             TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ---------------------------------------------------------------
-- RAG  (not in the original spec's table list at all - "pgvector /
-- Vector DB" was drawn as one box on an architecture diagram with no
-- concrete schema; this is that schema)
-- ---------------------------------------------------------------

CREATE TABLE document_chunks (
    id                     BIGSERIAL PRIMARY KEY,
    source_id              INT NOT NULL REFERENCES sources(id),
    chunk_index            INT NOT NULL,
    chunk_text             TEXT NOT NULL,
    -- Retrieval filters on these BEFORE ranking by distance. NULL means
    -- "applies generally", not "unknown": a NULL crop_id chunk is usable for
    -- any crop, a set one is usable for that crop only.
    state_id               INT REFERENCES states(id),
    crop_id                INT REFERENCES crops(id),
    season_id              INT REFERENCES seasons(id),
    product_id             INT REFERENCES products(id),
    -- voyage-3.5 at output_dimension 1024 (app/config.py EMBEDDING_DIM).
    -- Changing the model means re-embedding the whole corpus: vectors from
    -- two models are not comparable, and the mistake shows up as bad
    -- neighbours rather than as an error.
    embedding              VECTOR(1024),
    embedding_model        VARCHAR(100),
    -- Where the chunk came from inside its document, so a cited claim is
    -- traceable to a location and not just to an organisation name.
    page_start             INT,
    page_end               INT,
    char_start             INT,
    char_end               INT,
    token_count            INT,
    -- Makes re-ingest idempotent (skip unchanged chunks without re-embedding)
    -- and an accidental double-ingest detectable.
    content_sha256         CHAR(64),
    created_at             TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (source_id, chunk_index),
    CONSTRAINT chunk_embedding_has_model CHECK (embedding IS NULL OR embedding_model IS NOT NULL)
);
-- Metadata filter first (crop/state/season), THEN similarity search on the
-- filtered subset - the two-stage retrieval from the RAG dev plan, phase 3.
-- crop_id leads because it is the filter that must never be skipped.
CREATE INDEX idx_chunks_metadata ON document_chunks (crop_id, state_id, season_id);
-- HNSW, not IVFFlat: IVFFlat derives centroids from the rows present when the
-- index is built, so building it on the empty table this schema creates gives
-- meaningless centroids and poor recall until someone reindexes by hand. HNSW
-- needs no training pass and is correct from the first inserted row.
CREATE INDEX idx_chunks_embedding ON document_chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX idx_chunks_source ON document_chunks (source_id);
