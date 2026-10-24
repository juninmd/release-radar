from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

import httpx

from ..models import ReleaseCandidate
from ..resilience import post_json
from .text import strip_html

logger = logging.getLogger(__name__)

GRAPHQL_URL = "https://graphql.anilist.co"
_QUERY = """
query ($perPage: Int) {
  Page(perPage: $perPage) {
    media(type: ANIME, status: NOT_YET_RELEASED, sort: POPULARITY_DESC, isAdult: false) {
      id siteUrl description(asHtml: false) format episodes genres
      title { romaji english native }
      startDate { year month day }
      coverImage { extraLarge large }
      trailer { id site }
      studios(isMain: true) { nodes { name } }
    }
  }
}
"""


def fetch_anilist(client: httpx.Client, limit: int) -> list[ReleaseCandidate]:
    """Animes anunciados no AniList, por popularidade (GraphQL publico, sem API key)."""
    payload = post_json(
        client,
        GRAPHQL_URL,
        json={"query": _QUERY, "variables": {"perPage": min(max(limit, 1), 50)}},
    )
    media = ((payload.get("data") or {}).get("Page") or {}).get("media") or []
    candidates: list[ReleaseCandidate] = []
    for entry in media:
        candidate = _to_candidate(entry)
        if candidate is not None:
            candidates.append(candidate)
    return candidates[:limit]


def _to_candidate(entry: dict[str, Any]) -> ReleaseCandidate | None:
    anime_id = entry.get("id")
    url = str(entry.get("siteUrl") or "")
    titles: dict[str, Any] = entry.get("title") or {}
    title = str(titles.get("english") or titles.get("romaji") or titles.get("native") or "")
    if not anime_id or not url or not title:
        return None
    cover: dict[str, Any] = entry.get("coverImage") or {}
    return ReleaseCandidate(
        external_id=f"anilist:{anime_id}",
        title=title,
        url=url,
        channel="AniList",
        category="anime",
        duration=0,
        upload_date=datetime.now(UTC).strftime("%Y%m%d"),
        thumbnail=cover.get("extraLarge") or cover.get("large"),
        description=_description(entry, titles),
        source="anilist",
    )


def start_date(raw: Any) -> tuple[str, str]:
    """(data completa ISO, janela parcial). Datas parciais nao viram 'Estreia prevista'."""
    parts: dict[str, Any] = raw if isinstance(raw, dict) else {}
    year, month, day = parts.get("year"), parts.get("month"), parts.get("day")
    if not year:
        return "", ""
    if month and day:
        return f"{year:04d}-{month:02d}-{day:02d}", ""
    return "", f"{year:04d}-{month:02d}" if month else str(year)


def _description(entry: dict[str, Any], titles: dict[str, Any]) -> str:
    full_date, window = start_date(entry.get("startDate"))
    studios = ", ".join(
        str(node.get("name")) for node in (entry.get("studios") or {}).get("nodes") or []
    )
    genres = ", ".join(str(item) for item in entry.get("genres") or [])
    trailer: dict[str, Any] = entry.get("trailer") or {}
    trailer_url = (
        f"https://www.youtube.com/watch?v={trailer['id']}"
        if trailer.get("site") == "youtube" and trailer.get("id")
        else ""
    )
    original = titles.get("native")
    lines = [
        strip_html(entry.get("description")),
        f"Titulo original: {original}" if original else "",
        f"Estreia prevista: {full_date}" if full_date else "",
        f"Janela prevista: {window}" if window else "",
        f"Formato: {entry['format']}" if entry.get("format") else "",
        f"Episodios: {entry['episodes']}" if entry.get("episodes") else "",
        f"Generos: {genres}" if genres else "",
        f"Estudio: {studios}" if studios else "",
        f"Trailer: {trailer_url}" if trailer_url else "",
    ]
    return "\n".join(line for line in lines if line)
