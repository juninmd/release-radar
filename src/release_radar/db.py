from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

import psycopg2
from psycopg2.extras import Json, RealDictCursor

from .dedupe import backfill_work_keys
from .models import ReleaseAnalysis, ReleaseCandidate


def get_connection(dsn: str) -> psycopg2.extensions.connection:
    conn = psycopg2.connect(dsn, connect_timeout=10)
    conn.autocommit = False
    return conn


# Renomeia youtube_id -> external_id em bases criadas antes das fontes nao-YouTube.
# Reversivel: ALTER TABLE ... RENAME COLUMN external_id TO youtube_id.
_MIGRATIONS = """
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

-- Sem isto o indice antigo sobrevive ao rename e o CREATE INDEX abaixo duplicaria.
ALTER INDEX IF EXISTS idx_release_events_youtube_id RENAME TO idx_release_events_external_id;
"""


def init_db(dsn: str) -> None:
    conn = get_connection(dsn)
    try:
        with conn.cursor() as cur:
            cur.execute(_MIGRATIONS)
            cur.execute("""
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
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS release_events (
                    id BIGSERIAL PRIMARY KEY,
                    external_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    detail JSONB DEFAULT '{}'::jsonb,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
            cur.execute(
                "ALTER TABLE release_items "
                "ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'youtube'"
            )
            # Reversivel: DROP INDEX idx_release_items_work_key + DROP COLUMN work_key.
            cur.execute("ALTER TABLE release_items ADD COLUMN IF NOT EXISTS work_key TEXT")
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_release_items_work_key ON release_items(work_key)"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_release_items_status ON release_items(status)"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_release_items_category ON release_items(category)"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_release_events_external_id "
                "ON release_events(external_id)"
            )
        conn.commit()
        backfill_work_keys(conn)
    finally:
        conn.close()


def get_item(conn: psycopg2.extensions.connection, external_id: str) -> dict[str, Any] | None:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT * FROM release_items WHERE external_id = %s", (external_id,))
        row = cur.fetchone()
        return dict(row) if row else None


def reserve_candidate(
    conn: psycopg2.extensions.connection,
    candidate: ReleaseCandidate,
    content_hash: str,
    work_key: str | None = None,
) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO release_items
                (external_id, source, content_hash, title, url, channel, category, duration,
                 upload_date, thumbnail, description, work_key)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
            """,
            (
                candidate.external_id,
                candidate.source,
                content_hash,
                candidate.title,
                candidate.url,
                candidate.channel,
                candidate.category,
                candidate.duration,
                candidate.upload_date,
                candidate.thumbnail,
                candidate.description,
                work_key,
            ),
        )
        inserted = cur.rowcount == 1
    conn.commit()
    return inserted


def save_analysis(
    conn: psycopg2.extensions.connection,
    candidate: ReleaseCandidate,
    transcript: str,
    analysis: ReleaseAnalysis,
    work_key: str | None = None,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE release_items
            SET work_key = COALESCE(%s, work_key),
                transcript = %s,
                analysis = %s,
                analysis_summary = %s,
                is_release_signal = %s,
                status = %s,
                updated_at = NOW()
            WHERE external_id = %s
            """,
            (
                work_key,
                transcript,
                Json(analysis_to_json(analysis)),
                analysis.summary,
                analysis.is_release_signal,
                "analyzed" if analysis.is_release_signal else "skipped",
                candidate.external_id,
            ),
        )
        event_type = "analysis_saved" if analysis.is_release_signal else "analysis_skipped"
        cur.execute(
            "INSERT INTO release_events (external_id, event_type, detail) VALUES (%s, %s, %s)",
            (candidate.external_id, event_type, Json({"confidence": analysis.confidence})),
        )
    conn.commit()


def mark_posted(conn: psycopg2.extensions.connection, external_id: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE release_items
            SET status = 'posted', posted_at = NOW(), updated_at = NOW()
            WHERE external_id = %s
            """,
            (external_id,),
        )
        cur.execute(
            "INSERT INTO release_events (external_id, event_type) VALUES (%s, 'telegram_posted')",
            (external_id,),
        )
    conn.commit()


def mark_skipped(conn: psycopg2.extensions.connection, external_id: str, reason: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE release_items SET status = 'skipped', skipped_reason = %s, "
            "updated_at = NOW() WHERE external_id = %s",
            (reason, external_id),
        )
        cur.execute(
            "INSERT INTO release_events (external_id, event_type, detail) "
            "VALUES (%s, 'release_skipped', %s)",
            (external_id, Json({"reason": reason})),
        )
    conn.commit()


def mark_failed(
    conn: psycopg2.extensions.connection,
    external_id: str,
    reason: str,
    detail: dict[str, Any] | None = None,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE release_items
            SET status = 'failed', skipped_reason = %s, updated_at = NOW()
            WHERE external_id = %s
            """,
            (reason[:500], external_id),
        )
        cur.execute(
            "INSERT INTO release_events (external_id, event_type, detail) VALUES (%s, %s, %s)",
            (external_id, "failed", Json(detail or {"reason": reason})),
        )
    conn.commit()


def analysis_to_json(analysis: ReleaseAnalysis) -> dict[str, Any]:
    canonical = asdict(analysis)
    canonical.pop("raw")
    return json.loads(json.dumps({**analysis.raw, **canonical}, default=str))
