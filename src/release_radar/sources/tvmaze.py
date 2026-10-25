from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from ..models import ReleaseCandidate
from ..resilience import get_json
from .text import strip_html

logger = logging.getLogger(__name__)

SCHEDULE_URL = "https://api.tvmaze.com/schedule/web"
# Programas de auditorio, noticias e esporte nao sao "estreia" de serie.
_SHOW_TYPES = frozenset({"Scripted", "Animation", "Documentary"})


def fetch_tvmaze(
    client: httpx.Client,
    limit: int,
    days_ahead: int = 14,
    today: datetime | None = None,
) -> list[ReleaseCandidate]:
    """Estreias de series em streaming nos proximos dias (TVmaze, sem API key).

    So entram episodios 1x01 futuros; a data do episodio e a estreia oficial.
    """
    start = (today or datetime.now(UTC)).date()
    premieres: dict[int, tuple[int, ReleaseCandidate]] = {}
    for offset in range(1, days_ahead + 1):
        day = (start + timedelta(days=offset)).isoformat()
        episodes = _schedule(client, day)
        for episode in episodes:
            built = _to_candidate(episode)
            if built is not None:
                weight, candidate, show_id = built
                premieres.setdefault(show_id, (weight, candidate))
    ranked = sorted(premieres.values(), key=lambda item: item[0], reverse=True)
    return [candidate for _, candidate in ranked[:limit]]


def _schedule(client: httpx.Client, day: str) -> list[dict[str, Any]]:
    payload: Any = get_json(client, SCHEDULE_URL, params={"date": day})
    return payload if isinstance(payload, list) else []


def _to_candidate(episode: dict[str, Any]) -> tuple[int, ReleaseCandidate, int] | None:
    if episode.get("season") != 1 or episode.get("number") != 1:
        return None
    if episode.get("type") != "regular":
        return None
    show: dict[str, Any] = (episode.get("_embedded") or {}).get("show") or {}
    show_id = show.get("id")
    name = str(show.get("name") or "")
    airdate = str(episode.get("airdate") or "")
    if not isinstance(show_id, int) or not name or len(airdate) != 10:
        return None
    if show.get("type") not in _SHOW_TYPES:
        return None
    image: dict[str, Any] = show.get("image") or {}
    channel = _channel(show)
    weight = show.get("weight")
    candidate = ReleaseCandidate(
        external_id=f"tvmaze:{show_id}",
        title=name,
        url=str(show.get("officialSite") or show.get("url") or ""),
        channel=channel or "TVmaze",
        category="series",
        duration=0,
        upload_date=datetime.now(UTC).strftime("%Y%m%d"),
        thumbnail=image.get("original") or image.get("medium"),
        description=_description(show, airdate, channel),
        source="tvmaze",
    )
    if not candidate.url:
        return None
    return (weight if isinstance(weight, int) else 0), candidate, show_id


def _channel(show: dict[str, Any]) -> str:
    for key in ("webChannel", "network"):
        owner: dict[str, Any] = show.get(key) or {}
        if owner.get("name"):
            return str(owner["name"])
    return ""


def _description(show: dict[str, Any], airdate: str, channel: str) -> str:
    genres = ", ".join(str(item) for item in show.get("genres") or [])
    language = show.get("language")
    lines = [
        strip_html(show.get("summary")),
        f"Estreia prevista: {airdate}",
        f"Generos: {genres}" if genres else "",
        f"Idioma: {language}" if language else "",
        f"Plataforma: {channel}" if channel else "",
    ]
    return "\n".join(line for line in lines if line)
