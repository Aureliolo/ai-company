-- Ontology subsystem schema.
-- All statements use IF NOT EXISTS for idempotency.

-- ── Entity definitions ─────────────────────────────────────────

CREATE TABLE IF NOT EXISTS entity_definitions (
    name TEXT PRIMARY KEY CHECK(length(name) > 0),
    tier TEXT NOT NULL CHECK(tier IN ('core', 'user')),
    source TEXT NOT NULL CHECK(source IN ('auto', 'config', 'api')),
    definition TEXT NOT NULL DEFAULT '',
    fields TEXT NOT NULL DEFAULT '[]',
    constraints TEXT NOT NULL DEFAULT '[]',
    disambiguation TEXT NOT NULL DEFAULT '',
    relationships TEXT NOT NULL DEFAULT '[]',
    created_by TEXT NOT NULL CHECK(length(created_by) > 0),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ed_tier
    ON entity_definitions(tier);

-- ── Entity definition versions ─────────────────────────────────

CREATE TABLE IF NOT EXISTS entity_definition_versions (
    entity_id TEXT NOT NULL CHECK(length(entity_id) > 0),
    version INTEGER NOT NULL CHECK(version >= 1),
    content_hash TEXT NOT NULL CHECK(length(content_hash) > 0),
    snapshot TEXT NOT NULL CHECK(length(snapshot) > 0),
    saved_by TEXT NOT NULL CHECK(length(saved_by) > 0),
    saved_at TEXT NOT NULL CHECK(
        saved_at LIKE '%+00:00' OR saved_at LIKE '%Z'
    ),
    PRIMARY KEY (entity_id, version)
);

CREATE INDEX IF NOT EXISTS idx_edv_entity_saved
    ON entity_definition_versions(entity_id, saved_at DESC);
CREATE INDEX IF NOT EXISTS idx_edv_content_hash
    ON entity_definition_versions(entity_id, content_hash);
