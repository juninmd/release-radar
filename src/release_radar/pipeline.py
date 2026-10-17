from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from rich.console import Console
from rich.logging import RichHandler

from .analyzer import analyze_release
from .config import Settings
from .db import (
    get_connection,
    get_item,
    init_db,
    mark_failed,
    mark_posted,
    mark_skipped,
    reserve_candidate,
    save_analysis,
)
from .fingerprint import content_hash
from .models import ReleaseCandidate
from .release_policy import already_released, confirmed_upcoming
from .settings_store import effective_settings, read_overrides
from .sources import discover_extra_sources
from .telegram_bot import TelegramPublisher
from .transcriber import transcribe_audio
from .youtube import download_audio, enrich_candidate, get_channel_candidates

logger = logging.getLogger(__name__)

YOUTUBE_SOURCE = "youtube"


@dataclass
class RunStats:
    discovered: int = 0
    reserved: int = 0
    analyzed: int = 0
    posted: int = 0
    skipped_existing: int = 0
    skipped_not_release: int = 0
    skipped_released: int = 0
    skipped_unconfirmed: int = 0
    failed: int = 0


def configure_logging(verbose: bool = False) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(message)s",
        handlers=[RichHandler(console=Console(stderr=True), rich_tracebacks=True)],
    )


async def run_pipeline(
    settings: Settings,
    limit: int | None = None,
    dry_run: bool = False,
    dsn: str | None = None,
) -> RunStats:
    target = dsn or settings.postgres_dsn
    init_db(target)
    conn = get_connection(target)
    try:
        settings = effective_settings(settings, read_overrides(conn))
    except Exception:
        logger.exception("Failed to load settings overrides; using environment values")
    publisher = TelegramPublisher(settings.telegram_bot_token, settings.telegram_chat_id)
    stats = RunStats()
    max_items = limit or settings.max_items_per_run
    try:
        candidates = discover(settings)
        stats.discovered = len(candidates)
        logger.info("Discovered %s candidates", stats.discovered)
        for candidate in candidates:
            if stats.analyzed >= max_items:
                break
            enriched = (
                enrich_candidate(candidate, settings.yt_dlp_opts)
                if candidate.source == YOUTUBE_SOURCE
                else candidate
            )
            fingerprint = content_hash(enriched.title, enriched.channel, enriched.description)
            if get_item(conn, enriched.external_id):
                stats.skipped_existing += 1
                continue
            if not dry_run and not reserve_candidate(conn, enriched, fingerprint):
                stats.skipped_existing += 1
                continue
            if not dry_run:
                stats.reserved += 1
            try:
                transcript = maybe_transcribe(settings, enriched)
                analysis = analyze_release(
                    candidate=enriched,
                    transcript=transcript,
                    base_url=settings.llm_base_url,
                    api_key=settings.llm_api_key,
                    model=settings.llm_model,
                    timeout=settings.llm_timeout,
                )
                if not dry_run:
                    save_analysis(conn, enriched, transcript, analysis)
                stats.analyzed += 1
                if already_released(analysis):
                    if not dry_run:
                        mark_skipped(conn, enriched.external_id, "Obra ja lancada")
                    stats.skipped_released += 1
                    continue
                if not analysis.is_release_signal:
                    stats.skipped_not_release += 1
                    continue
                if not confirmed_upcoming(analysis):
                    if not dry_run:
                        mark_skipped(conn, enriched.external_id, "Estreia futura nao confirmada")
                    stats.skipped_unconfirmed += 1
                    continue
                if dry_run:
                    logger.info("Dry-run would post: %s", enriched.title)
                    continue
                if await publisher.publish(enriched, analysis):
                    mark_posted(conn, enriched.external_id)
                    stats.posted += 1
            except Exception as exc:
                stats.failed += 1
                logger.exception("Failed processing %s", enriched.external_id)
                if not dry_run:
                    mark_failed(conn, enriched.external_id, str(exc), {"title": enriched.title})
    finally:
        conn.close()
    return stats


def discover(settings: Settings) -> list[ReleaseCandidate]:
    candidates: list[ReleaseCandidate] = list(discover_extra_sources(settings))
    for category, channel in settings.parsed_sources:
        candidates.extend(
            get_channel_candidates(
                category=category,
                channel=channel,
                limit=settings.source_limit,
                max_duration=max(settings.max_transcription_seconds * 2, 900),
                extra_opts=settings.yt_dlp_opts,
            )
        )
    return interleave_by_source(candidates)


def interleave_by_source(candidates: list[ReleaseCandidate]) -> list[ReleaseCandidate]:
    """Alterna as fontes preservando recencia dentro de cada uma.

    Sem isso, feeds e lojas (datados do dia da coleta) ocupariam todo o
    max_items_per_run e os trailers do YouTube nunca seriam analisados.
    """
    grouped: dict[str, list[ReleaseCandidate]] = {}
    for candidate in candidates:
        grouped.setdefault(candidate.source, []).append(candidate)
    for items in grouped.values():
        items.sort(key=lambda item: item.upload_date or "", reverse=True)
    order = sorted(grouped, key=lambda name: (name != YOUTUBE_SOURCE, name))
    ordered: list[ReleaseCandidate] = []
    for index in range(max((len(items) for items in grouped.values()), default=0)):
        for name in order:
            items = grouped[name]
            if index < len(items):
                ordered.append(items[index])
    return ordered


def maybe_transcribe(settings: Settings, candidate: ReleaseCandidate) -> str:
    if not settings.analyze_video_content:
        return ""
    # Fontes sem video proprio (Steam, Kitsu, RSS) seguem so com metadados.
    if candidate.source != YOUTUBE_SOURCE:
        return ""
    if candidate.duration > settings.max_transcription_seconds:
        return ""
    try:
        audio_path = download_audio(candidate, settings.audio_dir)
        return transcribe_audio(audio_path, settings.whisper_base_url, settings.whisper_timeout)
    except Exception:
        logger.exception(
            "Transcription failed for %s; continuing with metadata only",
            candidate.external_id,
        )
        return ""


def run_sync(
    settings: Settings,
    limit: int | None = None,
    dry_run: bool = False,
    dsn: str | None = None,
) -> RunStats:
    return asyncio.run(run_pipeline(settings=settings, limit=limit, dry_run=dry_run, dsn=dsn))
