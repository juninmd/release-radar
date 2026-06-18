from __future__ import annotations

import json
from typing import Any

import psycopg2
from psycopg2.extras import Json, RealDictCursor

from .models import ReleaseAnalysis, ReleaseCandidate


def get_connection(dsn: str) -> psycopg2.extensions.connection:
    conn = psycopg2.connect(dsn)
    conn.autocommit = False
    return conn


def init_db(dsn: str) -> None:
    conn = get_connection(dsn)
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS release_items (
                    id BIGSERIAL PRIMARY KEY,
                    youtube_id TEXT NOT NULL UNIQUE,
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
                    youtube_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    detail JSONB DEFAULT '{}'::jsonb,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_release_items_status ON release_items(status)"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_release_items_category ON release_items(category)"
            )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_release_events_youtube_id "
                "ON release_events(youtube_id)"
            )
        conn.commit()
    finally:
        conn.close()


def get_item(conn: psycopg2.extensions.connection, youtube_id: str) -> dict[str, Any] | None:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT * FROM release_items WHERE youtube_id = %s", (youtube_id,))
        row = cur.fetchone()
        return dict(row) if row else None


def reserve_candidate(
    conn: psycopg2.extensions.connection,
    candidate: ReleaseCandidate,
    content_hash: str,
) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO release_items
                (youtube_id, content_hash, title, url, channel, category, duration,
                 upload_date, thumbnail, description)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
            """,
            (
                candidate.youtube_id,
                content_hash,
                candidate.title,
                candidate.url,
                candidate.channel,
                candidate.category,
                candidate.duration,
                candidate.upload_date,
                candidate.thumbnail,
                candidate.description,
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
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE release_items
            SET transcript = %s,
                analysis = %s,
                analysis_summary = %s,
                is_release_signal = %s,
                status = %s,
                updated_at = NOW()
            WHERE youtube_id = %s
            """,
            (
                transcript,
                Json(analysis.raw or analysis_to_json(analysis)),
                analysis.summary,
                analysis.is_release_signal,
                "analyzed" if analysis.is_release_signal else "skipped",
                candidate.youtube_id,
            ),
        )
        event_type = "analysis_saved" if analysis.is_release_signal else "analysis_skipped"
        cur.execute(
            "INSERT INTO release_events (youtube_id, event_type, detail) VALUES (%s, %s, %s)",
            (candidate.youtube_id, event_type, Json({"confidence": analysis.confidence})),
        )
    conn.commit()


def mark_posted(conn: psycopg2.extensions.connection, youtube_id: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE release_items
            SET status = 'posted', posted_at = NOW(), updated_at = NOW()
            WHERE youtube_id = %s
            """,
            (youtube_id,),
        )
        cur.execute(
            "INSERT INTO release_events (youtube_id, event_type) VALUES (%s, 'telegram_posted')",
            (youtube_id,),
        )
    conn.commit()


def mark_failed(
    conn: psycopg2.extensions.connection,
    youtube_id: str,
    reason: str,
    detail: dict[str, Any] | None = None,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE release_items
            SET status = 'failed', skipped_reason = %s, updated_at = NOW()
            WHERE youtube_id = %s
            """,
            (reason[:500], youtube_id),
        )
        cur.execute(
            "INSERT INTO release_events (youtube_id, event_type, detail) VALUES (%s, %s, %s)",
            (youtube_id, "failed", Json(detail or {"reason": reason})),
        )
    conn.commit()


def analysis_to_json(analysis: ReleaseAnalysis) -> dict[str, Any]:
    return json.loads(json.dumps(analysis.raw or analysis.__dict__, default=str))
