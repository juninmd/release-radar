-- Todas as chaves de identidade da obra (titulo original, PT-BR, titulo da fonte), para
-- que um repost seja barrado mesmo quando a LLM nomeia a obra de forma diferente.
-- Reversivel: DROP INDEX idx_release_items_work_keys + DROP COLUMN work_keys.
ALTER TABLE release_items ADD COLUMN IF NOT EXISTS work_keys TEXT[] NOT NULL DEFAULT '{}';
CREATE INDEX IF NOT EXISTS idx_release_items_work_keys ON release_items USING GIN (work_keys);
UPDATE release_items
SET work_keys = ARRAY[work_key]
WHERE work_key IS NOT NULL AND work_key <> '' AND work_keys = '{}';
