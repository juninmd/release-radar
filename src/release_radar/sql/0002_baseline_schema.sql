-- Esquema base. Tudo com IF NOT EXISTS: bases anteriores ao runner de migracoes
-- (que ja tem estas tabelas) apenas registram a versao.
CREATE TABLE IF NOT EXISTS release_items (
    id BIGSERIAL PRIMARY KEY,
    external_id TEXT NOT NULL UNIQUE,
    source TEXT NOT NULL DEFAULT 'youtube',
    content_hash TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    url TEXT NOT NULL UNIQUE,
    channel TEXT NOT NULL,
    category TEXT NOT NULL,
    duration INTEGER NOT NULL DEFAULT 0,
    upload_date TEXT,
    thumbnail TEXT,
    description TEXT DEFAULT '',
    transcript TEXT DEFAULT '',
    analysis JSONB DEFAULT '{}'::jsonb,
    analysis_summary TEXT DEFAULT '',
    is_release_signal BOOLEAN DEFAULT FALSE,
    status TEXT NOT NULL DEFAULT 'discovered',
    posted_at TIMESTAMP,
    skipped_reason TEXT DEFAULT '',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS release_events (
    id BIGSERIAL PRIMARY KEY,
    external_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    detail JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

ALTER TABLE release_items
    ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'youtube';

-- Reversivel: DROP INDEX idx_release_items_work_key + DROP COLUMN work_key.
ALTER TABLE release_items ADD COLUMN IF NOT EXISTS work_key TEXT;
CREATE INDEX IF NOT EXISTS idx_release_items_work_key ON release_items(work_key);
CREATE INDEX IF NOT EXISTS idx_release_items_status ON release_items(status);
CREATE INDEX IF NOT EXISTS idx_release_items_category ON release_items(category);
CREATE INDEX IF NOT EXISTS idx_release_events_external_id ON release_events(external_id);
