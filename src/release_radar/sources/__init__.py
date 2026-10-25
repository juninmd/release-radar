from __future__ import annotations

import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from functools import partial

import httpx

from ..config import Settings
from ..models import ReleaseCandidate
from .anilist import fetch_anilist
from .jikan import fetch_jikan
from .kitsu import fetch_kitsu
from .rss import fetch_rss
from .steam import fetch_steam
from .tvmaze import fetch_tvmaze
from .wikidata import KINDS as WIKIDATA_KINDS
from .wikidata import fetch_wikidata

logger = logging.getLogger(__name__)

USER_AGENT = "release-radar/0.1 (+https://github.com/juninmd/release-radar)"

MAX_PARALLEL_SOURCES = 6

__all__ = [
    "discover_extra_sources",
    "fetch_anilist",
    "fetch_jikan",
    "fetch_kitsu",
    "fetch_rss",
    "fetch_steam",
    "fetch_tvmaze",
    "fetch_wikidata",
]


SourceErrorHandler = Callable[[str, Exception], None]


def discover_extra_sources(
    settings: Settings, on_error: SourceErrorHandler | None = None
) -> list[ReleaseCandidate]:
    """Coleta as fontes que nao dependem do YouTube nem de API key.

    Uma fonte que falha nao derruba as outras; `on_error(nome, excecao)` permite contabilizar.
    """
    candidates: list[ReleaseCandidate] = []
    fetchers = _build_fetchers(settings)
    if not fetchers:
        return candidates
    with (
        httpx.Client(
            timeout=settings.http_timeout,
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
        ) as client,
        ThreadPoolExecutor(max_workers=min(MAX_PARALLEL_SOURCES, len(fetchers))) as pool,
    ):
        # Fontes sao independentes e I/O-bound: rodam em paralelo, mas o resultado
        # e coletado na ordem de registro para a rodada continuar deterministica.
        futures = [(name, pool.submit(fetcher, client)) for name, fetcher in fetchers]
        for name, future in futures:
            try:
                found = future.result()
            except Exception as exc:
                logger.error("Source %s failed", name, exc_info=exc)
                if on_error:
                    on_error(name, exc)
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
    if settings.anilist_enabled:
        fetchers.append(
            ("anilist", lambda client: fetch_anilist(client, limit=settings.anilist_limit))
        )
    if settings.jikan_enabled:
        fetchers.append(("jikan", lambda client: fetch_jikan(client, limit=settings.jikan_limit)))
    if settings.tvmaze_enabled:
        fetchers.append(
            (
                "tvmaze",
                lambda client: fetch_tvmaze(
                    client, limit=settings.tvmaze_limit, days_ahead=settings.tvmaze_days
                ),
            )
        )
    if settings.wikidata_enabled:
        # Um fetcher por tipo: o SPARQL e lento e os dois passam a rodar em paralelo.
        for kind in WIKIDATA_KINDS:
            fetchers.append(
                (
                    f"wikidata:{kind}",
                    partial(
                        fetch_wikidata,
                        kind=kind,
                        limit=settings.wikidata_limit,
                        days_ahead=settings.wikidata_days,
                    ),
                )
            )
    for category, feed_url in settings.parsed_rss_sources:
        fetchers.append(
            (
                f"rss:{feed_url}",
                partial(
                    fetch_rss,
                    feed_url=feed_url,
                    category=category,
                    limit=settings.rss_limit,
                ),
            )
        )
    return fetchers
