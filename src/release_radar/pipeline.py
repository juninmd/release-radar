from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from rich.logging import RichHandler

from .analyzer import analyze_release
from .config import Settings
from .db import (
    get_connection,
    get_item,
    init_db,
    mark_failed,
    mark_posted,
    reserve_candidate,
    save_analysis,
)
from .fingerprint import content_hash
from .models import ReleaseCandidate
from .telegram_bot import TelegramPublisher
from .transcriber import transcribe_audio
from .youtube import download_audio, enrich_candidate, get_channel_candidates

logger = logging.getLogger(__name__)


@dataclass
class RunStats:
    discovered: int = 0
    reserved: int = 0
    analyzed: int = 0
    posted: int = 0
    skipped_existing: int = 0
    skipped_not_release: int = 0
    failed: int = 0


def configure_logging(verbose: bool = False) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(message)s",
        handlers=[RichHandler(rich_tracebacks=True)],
    )


async def run_pipeline(
    settings: Settings,
    limit: int | None = None,
    dry_run: bool = False,
) -> RunStats:
    init_db(settings.postgres_dsn)
    conn = get_connection(settings.postgres_dsn)
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
            enriched = enrich_candidate(candidate)
            fingerprint = content_hash(enriched.title, enriched.channel, enriched.description)
            if get_item(conn, enriched.youtube_id):
                stats.skipped_existing += 1
                continue
            if not reserve_candidate(conn, enriched, fingerprint):
                stats.skipped_existing += 1
                continue
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
                save_analysis(conn, enriched, transcript, analysis)
                stats.analyzed += 1
                if not analysis.is_release_signal:
                    stats.skipped_not_release += 1
                    continue
                if dry_run:
                    logger.info("Dry-run would post: %s", enriched.title)
                    continue
                if await publisher.publish(enriched, analysis):
                    mark_posted(conn, enriched.youtube_id)
                    stats.posted += 1
            except Exception as exc:
                stats.failed += 1
                logger.exception("Failed processing %s", enriched.youtube_id)
                mark_failed(conn, enriched.youtube_id, str(exc), {"title": enriched.title})
    finally:
        conn.close()
    return stats


def discover(settings: Settings) -> list[ReleaseCandidate]:
    candidates: list[ReleaseCandidate] = []
    for category, channel in settings.parsed_sources:
        candidates.extend(
            get_channel_candidates(
                category=category,
                channel=channel,
                limit=settings.source_limit,
                max_duration=max(settings.max_transcription_seconds * 2, 900),
            )
        )
    candidates.sort(key=lambda item: item.upload_date or "", reverse=True)
    return candidates


def maybe_transcribe(settings: Settings, candidate: ReleaseCandidate) -> str:
    if not settings.analyze_video_content:
        return ""
    if candidate.duration > settings.max_transcription_seconds:
        return ""
    try:
        audio_path = download_audio(candidate, settings.audio_dir)
        return transcribe_audio(audio_path, settings.whisper_base_url, settings.whisper_timeout)
    except Exception:
        logger.exception(
            "Transcription failed for %s; continuing with metadata only",
            candidate.youtube_id,
        )
        return ""


def run_sync(settings: Settings, limit: int | None = None, dry_run: bool = False) -> RunStats:
    return asyncio.run(run_pipeline(settings=settings, limit=limit, dry_run=dry_run))
