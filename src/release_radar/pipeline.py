from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import asdict, dataclass, field

import psycopg2

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
from .dedupe import analysis_keys, candidate_keys, work_already_posted
from .fingerprint import content_hash
from .links import link_kind
from .logging_setup import configure_logging
from .models import ReleaseCandidate
from .release_policy import already_released, confirmed_upcoming, is_not_trailer
from .resilience import CircuitBreaker
from .settings_store import effective_settings, read_overrides
from .sources import discover_extra_sources
from .telegram_bot import TelegramPublisher
from .transcriber import transcribe_audio
from .work_identity import classify_video_title
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
    skipped_clip: int = 0
    skipped_duplicate: int = 0
    failed: int = 0
    # Observabilidade: onde a rodada gastou tempo e qual fonte esta falhando.
    candidates_by_source: dict[str, int] = field(default_factory=dict)
    source_errors: dict[str, int] = field(default_factory=dict)
    transcribed: int = 0
    transcription_failed: int = 0
    llm_seconds: float = 0.0
    duration_seconds: float = 0.0
    aborted: str = ""

    def record_source_error(self, source: str, exc: Exception | None = None) -> None:
        self.source_errors[source] = self.source_errors.get(source, 0) + 1


__all__ = ["RunStats", "configure_logging", "discover", "run_pipeline", "run_sync"]


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
        conn.rollback()
    publisher = TelegramPublisher(settings.telegram_bot_token, settings.telegram_chat_id)
    stats = RunStats()
    started = time.monotonic()
    max_items = limit or settings.max_items_per_run
    # Servicos externos fora do ar: depois de falhas seguidas, para de gastar timeout por item.
    llm_breaker = CircuitBreaker("llm", threshold=3, cooldown=300.0)
    whisper_breaker = CircuitBreaker("transcription", threshold=3, cooldown=300.0)
    try:
        candidates = discover(settings, stats)
        stats.discovered = len(candidates)
        for candidate in candidates:
            stats.candidates_by_source[candidate.source] = (
                stats.candidates_by_source.get(candidate.source, 0) + 1
            )
        logger.info("Discovered %s candidates", stats.discovered)
        for candidate in candidates:
            if stats.analyzed >= max_items:
                break
            if llm_breaker.is_open:
                stats.aborted = "llm_unavailable"
                logger.error("LLM unavailable; stopping the run to avoid burning candidates")
                break
            # Antes do enrich: evita uma ida ao yt-dlp para um item que ja conhecemos.
            if get_item(conn, candidate.external_id):
                stats.skipped_existing += 1
                continue
            enriched = (
                enrich_candidate(candidate, settings.yt_dlp_opts)
                if candidate.source == YOUTUBE_SOURCE
                else candidate
            )
            fingerprint = content_hash(enriched.title, enriched.channel, enriched.description)
            keys = candidate_keys(enriched)
            if not dry_run and not reserve_candidate(
                conn, enriched, fingerprint, keys[0] if keys else None
            ):
                stats.skipped_existing += 1
                continue
            if not dry_run:
                stats.reserved += 1
            is_video = link_kind(enriched.url, enriched.source) == "video"
            # Gates baratos antes de baixar audio/transcrever/chamar a LLM.
            if is_video and classify_video_title(enriched.title) == "clip":
                skip(conn, dry_run, enriched.external_id, "Clipe ou comentario, nao trailer")
                stats.skipped_clip += 1
                continue
            if work_already_posted(conn, keys):
                skip(conn, dry_run, enriched.external_id, "Trailer desta obra ja publicado")
                stats.skipped_duplicate += 1
                continue
            try:
                transcript = maybe_transcribe(settings, enriched, whisper_breaker, stats)
                llm_started = time.monotonic()
                try:
                    analysis = analyze_release(
                        candidate=enriched,
                        transcript=transcript,
                        base_url=settings.llm_base_url,
                        api_key=settings.llm_api_key,
                        model=settings.llm_model,
                        timeout=settings.llm_timeout,
                    )
                except Exception:
                    llm_breaker.record_failure()
                    raise
                finally:
                    stats.llm_seconds += time.monotonic() - llm_started
                llm_breaker.record_success()
                work_keys = analysis_keys(enriched, analysis)
                if not dry_run:
                    save_analysis(
                        conn, enriched, transcript, analysis, work_keys[0] if work_keys else None
                    )
                stats.analyzed += 1
                if already_released(analysis):
                    if not dry_run:
                        mark_skipped(conn, enriched.external_id, "Obra ja lancada")
                    stats.skipped_released += 1
                    continue
                if not analysis.is_release_signal:
                    stats.skipped_not_release += 1
                    continue
                if is_video and is_not_trailer(analysis):
                    skip(conn, dry_run, enriched.external_id, "Clipe ou comentario, nao trailer")
                    stats.skipped_clip += 1
                    continue
                if not confirmed_upcoming(analysis):
                    if not dry_run:
                        mark_skipped(conn, enriched.external_id, "Estreia futura nao confirmada")
                    stats.skipped_unconfirmed += 1
                    continue
                if work_already_posted(conn, [*keys, *work_keys]):
                    skip(conn, dry_run, enriched.external_id, "Trailer desta obra ja publicado")
                    stats.skipped_duplicate += 1
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
        stats.duration_seconds = round(time.monotonic() - started, 2)
        stats.llm_seconds = round(stats.llm_seconds, 2)
        logger.info("Run finished", extra={"event": "run_summary", **asdict(stats)})
    return stats


def skip(
    conn: psycopg2.extensions.connection, dry_run: bool, external_id: str, reason: str
) -> None:
    if not dry_run:
        mark_skipped(conn, external_id, reason)


def discover(settings: Settings, stats: RunStats | None = None) -> list[ReleaseCandidate]:
    on_error = stats.record_source_error if stats else None
    candidates: list[ReleaseCandidate] = list(discover_extra_sources(settings, on_error))
    for category, channel in settings.parsed_sources:
        candidates.extend(
            get_channel_candidates(
                category=category,
                channel=channel,
                limit=settings.source_limit,
                max_duration=max(settings.max_transcription_seconds * 2, 900),
                extra_opts=settings.yt_dlp_opts,
                on_error=on_error,
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


def maybe_transcribe(
    settings: Settings,
    candidate: ReleaseCandidate,
    breaker: CircuitBreaker | None = None,
    stats: RunStats | None = None,
) -> str:
    if not settings.analyze_video_content:
        return ""
    # Fontes sem video proprio (Steam, Kitsu, RSS) seguem so com metadados.
    if candidate.source != YOUTUBE_SOURCE:
        return ""
    if candidate.duration > settings.max_transcription_seconds:
        return ""
    if breaker and breaker.is_open:
        return ""
    try:
        audio_path = download_audio(candidate, settings.audio_dir)
        transcript = transcribe_audio(
            audio_path, settings.whisper_base_url, settings.whisper_timeout
        )
    except Exception:
        if breaker:
            breaker.record_failure()
        if stats:
            stats.transcription_failed += 1
        logger.exception(
            "Transcription failed for %s; continuing with metadata only",
            candidate.external_id,
        )
        return ""
    if breaker:
        breaker.record_success()
    if stats:
        stats.transcribed += 1
    return transcript


def run_sync(
    settings: Settings,
    limit: int | None = None,
    dry_run: bool = False,
    dsn: str | None = None,
) -> RunStats:
    return asyncio.run(run_pipeline(settings=settings, limit=limit, dry_run=dry_run, dsn=dsn))
