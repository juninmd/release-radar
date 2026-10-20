from __future__ import annotations

import html
import logging
import re
from datetime import UTC, datetime
from typing import Any

import httpx

from ..models import ReleaseCandidate
from ..resilience import get_json

logger = logging.getLogger(__name__)

SEARCH_URL = "https://store.steampowered.com/search/results/"
DETAILS_URL = "https://store.steampowered.com/api/appdetails"
# O endpoint de busca so devolve nome e imagem; o app id vive no path da capsule.
_APP_ID_RE = re.compile(r"/apps/(\d+)/")


def fetch_steam(
    client: httpx.Client,
    limit: int,
    country: str = "br",
    language: str = "portuguese",
) -> list[ReleaseCandidate]:
    """Jogos em 'em breve' mais populares da Steam (sem API key)."""
    candidates: list[ReleaseCandidate] = []
    for app_id in _search_upcoming(client, limit, country, language):
        # appdetails e rate-limited; um 429 no meio nao pode zerar o que ja foi coletado.
        try:
            candidate = _app_candidate(client, app_id, country, language)
        except Exception as exc:
            logger.warning("Steam appdetails failed for app %s: %s", app_id, exc)
            continue
        if candidate is not None:
            candidates.append(candidate)
        if len(candidates) >= limit:
            break
    return candidates


def _search_upcoming(client: httpx.Client, limit: int, country: str, language: str) -> list[str]:
    payload = get_json(
        client,
        SEARCH_URL,
        params={
            "query": "",
            "filter": "popularcomingsoon",
            "json": 1,
            "cc": country,
            "l": language,
            "count": max(limit * 2, 10),
        },
    )
    app_ids: list[str] = []
    for item in payload.get("items", []):
        match = _APP_ID_RE.search(str(item.get("logo") or ""))
        if not match:
            logger.debug("Steam item without app id: %s", item.get("name"))
            continue
        app_ids.append(match.group(1))
    return app_ids


def _app_candidate(
    client: httpx.Client, app_id: str, country: str, language: str
) -> ReleaseCandidate | None:
    payload = (
        get_json(client, DETAILS_URL, params={"appids": app_id, "cc": country, "l": language}).get(
            app_id
        )
        or {}
    )
    if not payload.get("success"):
        return None
    data: dict[str, Any] = payload.get("data") or {}
    if data.get("type") != "game":
        return None
    release = data.get("release_date") or {}
    if not release.get("coming_soon"):
        return None
    return ReleaseCandidate(
        external_id=f"steam:{app_id}",
        title=str(data.get("name") or f"Steam app {app_id}"),
        url=f"https://store.steampowered.com/app/{app_id}/",
        channel="Steam",
        category="games",
        duration=0,
        # A Steam nao expoe data de anuncio; usamos a data da coleta para ordenar.
        upload_date=datetime.now(UTC).strftime("%Y%m%d"),
        thumbnail=data.get("header_image"),
        description=_description(data, release),
        source="steam",
    )


def _description(data: dict[str, Any], release: dict[str, Any]) -> str:
    genres = ", ".join(str(item.get("description")) for item in data.get("genres") or [])
    developers = ", ".join(str(item) for item in data.get("developers") or [])
    publishers = ", ".join(str(item) for item in data.get("publishers") or [])
    movies = data.get("movies") or []
    lines = [
        html.unescape(str(data.get("short_description") or "")),
        f"Lancamento previsto: {release.get('date') or 'desconhecido'}",
        f"Generos: {genres}" if genres else "",
        f"Desenvolvedora: {developers}" if developers else "",
        f"Publicadora: {publishers}" if publishers else "",
        f"Trailers na loja: {len(movies)}" if movies else "",
        "Plataforma: PC (Steam)",
    ]
    return "\n".join(line for line in lines if line)
