from __future__ import annotations

import logging
from collections.abc import Callable

import httpx

from ..config import Settings
from ..models import ReleaseCandidate
from .kitsu import fetch_kitsu
from .rss import fetch_rss
from .steam import fetch_steam

logger = logging.getLogger(__name__)

USER_AGENT = "release-radar/0.1 (+https://github.com/juninmd/release-radar)"

__all__ = ["discover_extra_sources", "fetch_kitsu", "fetch_rss", "fetch_steam"]


def discover_extra_sources(settings: Settings) -> list[ReleaseCandidate]:
    """Coleta as fontes que nao dependem do YouTube nem de API key."""
    candidates: list[ReleaseCandidate] = []
    fetchers = _build_fetchers(settings)
    if not fetchers:
        return candidates
    with httpx.Client(
        timeout=settings.http_timeout,
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
    ) as client:
        for name, fetcher in fetchers:
            try:
                found = fetcher(client)
            except Exception:
                logger.exception("Source %s failed", name)
                continue
            logger.info("Source %s returned %s candidates", name, len(found))
            candidates.extend(found)
    return candidates


def _build_fetchers(
    settings: Settings,
) -> list[tuple[str, Callable[[httpx.Client], list[ReleaseCandidate]]]]:
    fetchers: list[tuple[str, Callable[[httpx.Client], list[ReleaseCandidate]]]] = []
    if settings.steam_enabled:
        fetchers.append(
            (
                "steam",
                lambda client: fetch_steam(
                    client,
                    limit=settings.steam_limit,
                    country=settings.steam_country,
                    language=settings.steam_language,
                ),
            )
        )
    if settings.kitsu_enabled:
        fetchers.append(("kitsu", lambda client: fetch_kitsu(client, limit=settings.kitsu_limit)))
    for category, feed_url in settings.parsed_rss_sources:
        fetchers.append(
            (
                f"rss:{feed_url}",
                lambda client, url=feed_url, cat=category: fetch_rss(
                    client, feed_url=url, category=cat, limit=settings.rss_limit
                ),
            )
        )
    return fetchers
