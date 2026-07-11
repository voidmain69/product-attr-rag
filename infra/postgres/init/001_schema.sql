-- Canonical Fact Store schema (docs/04-storage-indexing.md).
-- Applied automatically on first `docker compose up` (empty data dir only).
-- Schema changes go through new numbered migration files, never by editing this one.

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ---------------------------------------------------------------------------
-- products — resolved product entities (docs/03 §4 entity resolution)
-- ---------------------------------------------------------------------------
CREATE TABLE products (
    product_id      TEXT PRIMARY KEY,          -- prd_<ulid>
    brand           TEXT NOT NULL,
    model           TEXT NOT NULL,
    category_path   TEXT[] NOT NULL DEFAULT '{}',
    gtin            TEXT,
    mpn             TEXT,
    canonical_title TEXT,
    source_urls     TEXT[] NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX products_gtin_idx ON products (gtin) WHERE gtin IS NOT NULL;
CREATE INDEX products_mpn_brand_idx  ON products (mpn, brand) WHERE mpn IS NOT NULL;
CREATE INDEX products_brand_model_idx ON products (brand, model);
CREATE INDEX products_category_idx   ON products USING GIN (category_path);

-- ---------------------------------------------------------------------------
-- attributes_ontology — canonical, versioned attribute ontology (docs/03 §1)
-- ---------------------------------------------------------------------------
CREATE TABLE attributes_ontology (
    attribute_key     TEXT NOT NULL,
    ontology_version  INT  NOT NULL,
    category_path     TEXT[] NOT NULL DEFAULT '{}',
    display_name      JSONB NOT NULL DEFAULT '{}',   -- {"uk": "...", "en": "..."}
    data_type         TEXT NOT NULL CHECK (data_type IN
                        ('quantity','enum','boolean','text','range','date')),
    canonical_unit    TEXT,
    allowed_units     TEXT[] NOT NULL DEFAULT '{}',
    value_constraints JSONB,                          -- {"min": 0, "max": 500000}
    enum_values       TEXT[],
    synonyms          TEXT[] NOT NULL DEFAULT '{}',
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (attribute_key, ontology_version)
);

CREATE INDEX ontology_synonyms_idx ON attributes_ontology USING GIN (synonyms);

-- ---------------------------------------------------------------------------
-- facts — append-only versioned facts, the heart of the system (docs/04 §2-3)
-- ---------------------------------------------------------------------------
CREATE TABLE facts (
    fact_id          TEXT PRIMARY KEY,          -- fct_<ulid>
    product_id       TEXT NOT NULL REFERENCES products (product_id),
    attribute_key    TEXT NOT NULL,
    ontology_version INT  NOT NULL,
    data_type        TEXT NOT NULL,
    canonical_value  JSONB,                     -- number | string | bool | {"min","max"}
    canonical_unit   TEXT,
    original_value   TEXT NOT NULL,
    effective        BOOLEAN NOT NULL DEFAULT TRUE,
    disputed         BOOLEAN NOT NULL DEFAULT FALSE,
    confidence       REAL NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    provenance       JSONB NOT NULL,            -- source_type, url, tier, span, fetched_at
    valid_from       TIMESTAMPTZ NOT NULL DEFAULT now(),
    superseded_by    TEXT REFERENCES facts (fact_id)
);

-- Instant exact lookup: the main answering route (docs/05 §3)
CREATE INDEX facts_lookup_idx ON facts (product_id, attribute_key)
    WHERE effective AND superseded_by IS NULL;
CREATE INDEX facts_attribute_idx ON facts (attribute_key) WHERE effective;
CREATE INDEX facts_provenance_idx ON facts USING GIN (provenance);

-- ---------------------------------------------------------------------------
-- mapping_dictionary — confirmed raw_attribute -> attribute_key mappings
-- (HITL loop closure, docs/03 §2.1/§2.4)
-- ---------------------------------------------------------------------------
CREATE TABLE mapping_dictionary (
    raw_attribute  TEXT NOT NULL,
    language       TEXT NOT NULL DEFAULT 'und',
    category_path  TEXT[] NOT NULL DEFAULT '{}',
    attribute_key  TEXT NOT NULL,
    confirmed_by   TEXT NOT NULL DEFAULT 'auto',  -- auto | hitl:<user>
    confirmed_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (raw_attribute, language, category_path)
);

-- ---------------------------------------------------------------------------
-- sources — source registry with legal status (docs/01 §5)
-- ---------------------------------------------------------------------------
CREATE TABLE sources (
    domain          TEXT PRIMARY KEY,
    access_channel  TEXT NOT NULL CHECK (access_channel IN
                      ('feed','api','scrape','forbidden')),
    robots_status   TEXT,
    tos_notes       TEXT,
    detected_engine TEXT,                        -- shopify | woocommerce | bitrix | ...
    crawl_policy    JSONB NOT NULL DEFAULT '{}', -- {"rps": 0.5, "crawl_delay": 2}
    legal_checked_at TIMESTAMPTZ,
    quarantined_until TIMESTAMPTZ
);

-- ---------------------------------------------------------------------------
-- raw_artifacts — metadata for objects living in the S3 raw store (docs/01 §7)
-- ---------------------------------------------------------------------------
CREATE TABLE raw_artifacts (
    raw_artifact_id TEXT PRIMARY KEY,            -- s3 key
    url             TEXT NOT NULL,
    canonical_url   TEXT NOT NULL,
    fetched_at      TIMESTAMPTZ NOT NULL,
    http_status     INT NOT NULL,
    content_type    TEXT,
    content_hash    TEXT NOT NULL,
    render_mode     TEXT NOT NULL CHECK (render_mode IN ('static_http','headless')),
    detected_engine TEXT,
    proxy_region    TEXT,
    robots_allowed  BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE INDEX raw_artifacts_url_idx  ON raw_artifacts (canonical_url, fetched_at DESC);
CREATE INDEX raw_artifacts_hash_idx ON raw_artifacts (content_hash);

-- ---------------------------------------------------------------------------
-- chunks — self-contained chunks for hybrid retrieval (docs/04 §4-5)
-- ---------------------------------------------------------------------------
CREATE TABLE chunks (
    chunk_id      TEXT PRIMARY KEY,              -- chk_<ulid>
    product_id    TEXT NOT NULL REFERENCES products (product_id),
    kind          TEXT NOT NULL CHECK (kind IN ('fact','rich')),
    body          TEXT NOT NULL,                 -- serialized self-contained text
    fact_ids      TEXT[] NOT NULL DEFAULT '{}',  -- chunk -> facts -> source_span
    attribute_keys TEXT[] NOT NULL DEFAULT '{}',
    brand         TEXT,
    category_path TEXT[] NOT NULL DEFAULT '{}',
    source_url    TEXT,
    fetched_at    TIMESTAMPTZ,
    embedding     VECTOR(1024),                  -- multilingual embedding model
    stale         BOOLEAN NOT NULL DEFAULT FALSE -- set when source facts change
);

CREATE INDEX chunks_product_idx  ON chunks (product_id);
CREATE INDEX chunks_filter_idx   ON chunks (brand) INCLUDE (category_path);
CREATE INDEX chunks_attrs_idx    ON chunks USING GIN (attribute_keys);
-- HNSW index for dense retrieval; rebuilt on embedding-model change (docs/04 §7)
CREATE INDEX chunks_embedding_idx ON chunks
    USING hnsw (embedding vector_cosine_ops);

-- ---------------------------------------------------------------------------
-- hitl_queue — human-in-the-loop moderation queues (docs/06 §4)
-- ---------------------------------------------------------------------------
CREATE TABLE hitl_queue (
    item_id     TEXT PRIMARY KEY,
    queue       TEXT NOT NULL CHECK (queue IN
                  ('attribute_mapping','low_confidence_fact','disputed_fact',
                   'entity_resolution','value_anomaly')),
    payload     JSONB NOT NULL,
    priority    INT NOT NULL DEFAULT 100,        -- lower = more urgent
    status      TEXT NOT NULL DEFAULT 'open'
                  CHECK (status IN ('open','resolved','rejected')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at TIMESTAMPTZ,
    resolved_by TEXT,
    resolution  JSONB
);

CREATE INDEX hitl_open_idx ON hitl_queue (queue, priority) WHERE status = 'open';
