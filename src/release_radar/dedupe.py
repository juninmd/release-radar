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
    """Chaves da obra pelo titulo da fonte; manchete de artigo nao e titulo de obra."""
    if link_kind(candidate.url, candidate.source) == "article":
        return []
    return _unique_keys([candidate.title], candidate.category, candidate.channel)


def analysis_keys(candidate: ReleaseCandidate, analysis: ReleaseAnalysis) -> list[str]:
    # Sem LLM, original_title e a propria manchete: nao identifica obra nenhuma.
    if link_kind(candidate.url, candidate.source) == "article" and analysis.raw.get("fallback"):
        return []
    category = analysis.category if analysis.category != "unknown" else candidate.category
    return _unique_keys([analysis.original_title, analysis.title], category, candidate.channel)


def merge_keys(*groups: Iterable[str]) -> list[str]:
    """Une grupos de chaves sem repetir, preservando a ordem (a primeira e a principal)."""
    return list(dict.fromkeys(key for group in groups for key in group if key))


def work_already_posted(conn: psycopg2.extensions.connection, keys: Iterable[str]) -> bool:
    wanted = [key for key in keys if key]
    if not wanted:
        return False
    with conn.cursor() as cur:
        cur.execute(
            """SELECT 1 FROM release_items
               WHERE status = 'posted' AND (work_keys && %s OR work_key = ANY(%s)) LIMIT 1""",
            (wanted, wanted),
        )
        posted = cur.fetchone() is not None
    # Leitura nao deve deixar transacao aberta entre chamadas externas.
    conn.commit()
    return posted


def row_work_keys(row: Mapping[str, Any]) -> list[str]:
    """Chaves de uma linha ja gravada; vazio para clipe (nunca casa com nada)."""
    if row.get("work_keys"):
        return [str(key) for key in row["work_keys"]]
    if row.get("work_key"):
        return [str(row["work_key"])]
    kind = link_kind(row["url"], row["source"])
    data = row["analysis"] if isinstance(row.get("analysis"), dict) else {}
    # Clipe publicado antes do filtro nao pode bloquear o trailer de verdade da obra.
    if kind == "video" and (
        data.get("content_type") in {"clip", "other"}
        or classify_video_title(row["title"]) == "clip"
    ):
        return []
    category = str(data.get("category") or "")
    category = category if category not in {"", "unknown"} else row["category"]
    titles = [str(data.get("original_title") or ""), str(data.get("title") or row["title"])]
    if kind == "article" and data.get("fallback"):
        return []
    return _unique_keys(titles, category, row["channel"])


def backfill_work_keys(conn: psycopg2.extensions.connection) -> None:
    """Linhas publicadas antes das colunas ganham chaves."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """SELECT external_id, source, url, title, channel, category, analysis
               FROM release_items
               WHERE status = 'posted' AND (work_key IS NULL OR work_keys = '{}')"""
        )
        rows = cur.fetchall()
    with conn.cursor() as cur:
        for row in rows:
            keys = row_work_keys({**row, "work_key": None, "work_keys": None})
            cur.execute(
                "UPDATE release_items SET work_key = %s, work_keys = %s WHERE external_id = %s",
                (keys[0] if keys else "", keys, row["external_id"]),
            )
    conn.commit()
