from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

import httpx

from ..models import ReleaseCandidate
from ..resilience import get_json
from .text import strip_html

logger = logging.getLogger(__name__)

UPCOMING_URL = "https://api.jikan.moe/v4/seasons/upcoming"


def fetch_jikan(client: httpx.Client, limit: int) -> list[ReleaseCandidate]:
    """Animes da proxima temporada no MyAnimeList via Jikan (sem API key)."""
    payload = get_json(
        client, UPCOMING_URL, params={"limit": min(max(limit, 1), 25), "sfw": "true"}
    )
    candidates: list[ReleaseCandidate] = []
    seen: set[object] = set()
    for entry in payload.get("data") or []:
        candidate = _to_candidate(entry)
        if candidate is None or candidate.external_id in seen:
            continue
        seen.add(candidate.external_id)
        candidates.append(candidate)
    return candidates[:limit]


def _to_candidate(entry: dict[str, Any]) -> ReleaseCandidate | None:
    mal_id = entry.get("mal_id")
    url = str(entry.get("url") or "")
    title = str(entry.get("title_english") or entry.get("title") or "")
    if not mal_id or not url or not title:
        return None
    jpg: dict[str, Any] = (entry.get("images") or {}).get("jpg") or {}
    return ReleaseCandidate(
        external_id=f"jikan:{mal_id}",
        title=title,
        url=url,
        channel="MyAnimeList",
        category="anime",
        duration=0,
        upload_date=datetime.now(UTC).strftime("%Y%m%d"),
        thumbnail=jpg.get("large_image_url") or jpg.get("image_url"),
        description=_description(entry),
        source="jikan",
    )


def _aired_from(entry: dict[str, Any]) -> tuple[str, str]:
    """(data completa ISO, texto livre). `aired.from` e null enquanto nao ha data."""
    aired: dict[str, Any] = entry.get("aired") or {}
    raw = str(aired.get("from") or "")
    if len(raw) >= 10 and raw[4] == "-" and raw[7] == "-":
        return raw[:10], ""
    text = str(aired.get("string") or "")
    return "", "" if text.lower() in {"", "not available"} else text


def _description(entry: dict[str, Any]) -> str:
    full_date, window = _aired_from(entry)
    genres = ", ".join(str(item.get("name")) for item in entry.get("genres") or [])
    studios = ", ".join(str(item.get("name")) for item in entry.get("studios") or [])
    trailer: dict[str, Any] = entry.get("trailer") or {}
    original = entry.get("title_japanese")
    lines = [
        strip_html(entry.get("synopsis")),
        f"Titulo original: {original}" if original else "",
        f"Estreia prevista: {full_date}" if full_date else "",
        f"Janela prevista: {window}" if window else "",
        f"Formato: {entry['type']}" if entry.get("type") else "",
        f"Episodios: {entry['episodes']}" if entry.get("episodes") else "",
        f"Generos: {genres}" if genres else "",
        f"Estudio: {studios}" if studios else "",
        f"Trailer: {trailer['url']}" if trailer.get("url") else "",
    ]
    return "\n".join(line for line in lines if line)
