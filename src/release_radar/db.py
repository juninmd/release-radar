from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

import psycopg2
from psycopg2.extras import Json, RealDictCursor

from .dedupe import backfill_work_keys
from .migrations import apply_migrations
from .models import ReleaseAnalysis, ReleaseCandidate


def get_connection(dsn: str) -> psycopg2.extensions.connection:
    conn = psycopg2.connect(dsn, connect_timeout=10)
    conn.autocommit = False
    return conn


def init_db(dsn: str) -> None:
    conn = get_connection(dsn)
    try:
        apply_migrations(conn)
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
