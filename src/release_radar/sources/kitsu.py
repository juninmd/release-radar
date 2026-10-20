from __future__ import annotations

import logging
from typing import Any

import httpx

from ..models import ReleaseCandidate
from ..resilience import get_json

logger = logging.getLogger(__name__)

ANIME_URL = "https://kitsu.io/api/edge/anime"


def fetch_kitsu(client: httpx.Client, limit: int) -> list[ReleaseCandidate]:
    """Animes anunciados/aguardados no Kitsu, ordenados por audiencia (sem API key)."""
    payload = get_json(
        client,
        ANIME_URL,
        params={
            "filter[status]": "upcoming",
            "sort": "-userCount",
            "page[limit]": min(limit, 20),
        },
        headers={"Accept": "application/vnd.api+json"},
    )
    candidates: list[ReleaseCandidate] = []
    for entry in payload.get("data", []):
        candidate = _to_candidate(entry)
        if candidate is not None:
            candidates.append(candidate)
    return candidates[:limit]


def _to_candidate(entry: dict[str, Any]) -> ReleaseCandidate | None:
    anime_id = str(entry.get("id") or "")
    attributes: dict[str, Any] = entry.get("attributes") or {}
    slug = str(attributes.get("slug") or "")
    if not anime_id or not slug:
        return None
    titles: dict[str, Any] = attributes.get("titles") or {}
    title = str(titles.get("en") or attributes.get("canonicalTitle") or titles.get("en_jp") or slug)
    poster: dict[str, Any] = attributes.get("posterImage") or {}
    return ReleaseCandidate(
        external_id=f"kitsu:{anime_id}",
        title=title,
        url=f"https://kitsu.io/anime/{slug}",
        channel="Kitsu",
        category="anime",
        duration=0,
        upload_date=_updated_date(attributes.get("updatedAt")),
        thumbnail=poster.get("original") or poster.get("large"),
        description=_description(attributes, titles),
        source="kitsu",
    )


def _updated_date(raw: Any) -> str | None:
    """updatedAt ISO-8601 -> YYYYMMDD, mesmo formato do yt-dlp usado na ordenacao."""
    text = str(raw or "")
    if len(text) < 10:
        return None
    return text[:10].replace("-", "")


def _description(attributes: dict[str, Any], titles: dict[str, Any]) -> str:
    original = titles.get("ja_jp") or titles.get("en_jp")
    fmt = attributes.get("showType") or attributes.get("subtype")
    trailer_id = attributes.get("youtubeVideoId")
    episodes = attributes.get("episodeCount")
    lines = [
        str(attributes.get("synopsis") or attributes.get("description") or ""),
        f"Titulo original: {original}" if original else "",
        f"Estreia prevista: {attributes.get('startDate') or 'desconhecida'}",
        f"Formato: {fmt}" if fmt else "",
        f"Episodios: {episodes}" if episodes else "",
        f"Trailer: https://www.youtube.com/watch?v={trailer_id}" if trailer_id else "",
    ]
    return "\n".join(line for line in lines if line)
