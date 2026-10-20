-- Renomeia youtube_id -> external_id em bases criadas antes das fontes nao-YouTube.
-- Idempotente; reversivel: ALTER TABLE ... RENAME COLUMN external_id TO youtube_id.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = 'release_items' AND column_name = 'youtube_id'
    ) THEN
        ALTER TABLE release_items RENAME COLUMN youtube_id TO external_id;
    END IF;
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = 'release_events' AND column_name = 'youtube_id'
    ) THEN
        ALTER TABLE release_events RENAME COLUMN youtube_id TO external_id;
    END IF;
END $$;

-- Sem isto o indice antigo sobrevive ao rename e o CREATE INDEX duplicaria.
ALTER INDEX IF EXISTS idx_release_events_youtube_id RENAME TO idx_release_events_external_id;
