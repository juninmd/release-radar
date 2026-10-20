-- Overrides de configuracao editaveis pelo painel/app desktop (ver settings_store.py).
CREATE TABLE IF NOT EXISTS radar_settings (
    key TEXT PRIMARY KEY,
    value JSONB NOT NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);
