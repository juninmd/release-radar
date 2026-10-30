from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

import psycopg2
from psycopg2.extras import RealDictCursor

from .links import link_kind
from .models import ReleaseAnalysis, ReleaseCandidate
from .work_identity import classify_video_title, work_key


def _unique_keys(titles: Iterable[str], category: str, channel: str) -> list[str]:
    keys = [work_key(title, category, channel) for title in titles if title.strip()]
    return list(dict.fromkeys(key for key in keys if key))


def candidate_keys(candidate: ReleaseCandidate) -> list[str]:
    """Chave da obra pelo titulo do video; so videos competem por 'o mesmo trailer'."""
    if link_kind(candidate.url, candidate.source) != "video":
        return []
    return _unique_keys([candidate.title], candidate.category, candidate.channel)


def analysis_keys(candidate: ReleaseCandidate, analysis: ReleaseAnalysis) -> list[str]:
    if link_kind(candidate.url, candidate.source) != "video":
        return []
    category = analysis.category if analysis.category != "unknown" else candidate.category
    return _unique_keys([analysis.original_title, analysis.title], category, candidate.channel)


def work_already_posted(conn: psycopg2.extensions.connection, keys: Iterable[str]) -> bool:
    wanted = [key for key in keys if key]
    if not wanted:
        return False
    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM release_items WHERE status = 'posted' AND work_key = ANY(%s) LIMIT 1",
            (wanted,),
        )
        posted = cur.fetchone() is not None
    # Leitura nao deve deixar transacao aberta entre chamadas externas.
    conn.commit()
    return posted


def row_work_key(row: Mapping[str, Any]) -> str:
    """Chave de uma linha ja gravada; '' para o que nao e video (nunca casa com nada)."""
    if row.get("work_key") is not None:
        return str(row["work_key"])
    if link_kind(row["url"], row["source"]) != "video":
        return ""
    data = row["analysis"] if isinstance(row.get("analysis"), dict) else {}
    # Clipe publicado antes do filtro nao pode bloquear o trailer de verdade da obra.
    if (
        data.get("content_type") in {"clip", "other"}
        or classify_video_title(row["title"]) == "clip"
    ):
        return ""
    category = str(data.get("category") or "")
    keys = _unique_keys(
        [str(data.get("original_title") or ""), str(data.get("title") or row["title"])],
        category if category not in {"", "unknown"} else row["category"],
        row["channel"],
    )
    return keys[0] if keys else ""


def backfill_work_keys(conn: psycopg2.extensions.connection) -> None:
    """Linhas publicadas antes da coluna ganham chave."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """SELECT external_id, source, url, title, channel, category, analysis
               FROM release_items WHERE work_key IS NULL AND status = 'posted'"""
        )
        rows = cur.fetchall()
    with conn.cursor() as cur:
        for row in rows:
            cur.execute(
                "UPDATE release_items SET work_key = %s WHERE external_id = %s",
                (row_work_key({**row, "work_key": None}), row["external_id"]),
            )
    conn.commit()
