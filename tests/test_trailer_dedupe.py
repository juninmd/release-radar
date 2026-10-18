"""Trailers repetidos da mesma obra e clipes nao chegam ao Telegram nem ao painel."""

from __future__ import annotations

import asyncio

import pytest

from release_radar import pipeline
from release_radar.analyzer import analysis_from_json, fallback_analysis
from release_radar.config import Settings
from release_radar.db import get_connection, init_db, mark_posted, reserve_candidate
from release_radar.models import ReleaseCandidate
from release_radar.web import list_releases


def video(video_id: str, title: str, channel: str = "Canal") -> ReleaseCandidate:
    return ReleaseCandidate(
        external_id=video_id,
        title=title,
        url=f"https://www.youtube.com/watch?v={video_id}",
        channel=channel,
        category="movies",
        duration=120,
        upload_date="20260901",
        thumbnail=None,
        description="Estreia em 2027.",
    )


class FakePublisher:
    def __init__(self, *_args) -> None:
        self.published: list[str] = []

    async def publish(self, candidate, _analysis) -> bool:
        self.published.append(candidate.title)
        return True


@pytest.fixture
def radar(postgres_dsn: str, monkeypatch):
    """Roda o pipeline real com descoberta e LLM falsos contra o Postgres de teste."""
    init_db(postgres_dsn)
    publisher = FakePublisher()
    monkeypatch.setattr(pipeline, "TelegramPublisher", lambda *_a: publisher)
    monkeypatch.setattr(pipeline, "enrich_candidate", lambda candidate, _opts: candidate)
    monkeypatch.setattr(pipeline, "maybe_transcribe", lambda *_a: "")

    def analyze(candidate, **_kwargs):
        data = {
            "is_release_signal": True,
            "release_status": "upcoming",
            "title": "Duna: Parte Tres",
            "original_title": "Dune: Part Three",
            "content_type": "trailer",
        }
        return analysis_from_json(candidate, data)

    monkeypatch.setattr(pipeline, "analyze_release", analyze)

    def run(*candidates: ReleaseCandidate, analyze_with=None):
        if analyze_with:
            monkeypatch.setattr(pipeline, "analyze_release", analyze_with)
        monkeypatch.setattr(pipeline, "discover", lambda _settings: list(candidates))
        settings = Settings(_env_file=None)
        monkeypatch.setattr(Settings, "postgres_dsn", property(lambda _self: postgres_dsn))
        return asyncio.run(pipeline.run_pipeline(settings))

    return run, publisher


def test_second_trailer_of_the_same_work_is_not_published(radar) -> None:
    run, publisher = radar

    first = run(video("a1", "Dune: Part Three | Official Trailer"))
    second = run(
        video("a2", "Dune: Part Three - Final Trailer"),
        video("a3", "Dune Part Three (TV Spot)"),
    )

    assert first.posted == 1
    assert (second.posted, second.skipped_duplicate) == (0, 2)
    assert publisher.published == ["Dune: Part Three | Official Trailer"]


def test_duplicate_found_only_after_analysis_still_blocks_publication(radar) -> None:
    run, publisher = radar
    run(video("b1", "Dune: Part Three | Official Trailer"))

    stats = run(video("b2", "Duna 3 chegando em breve"))

    # Titulo diferente, mas a analise identifica a mesma obra (original_title igual).
    assert (stats.posted, stats.skipped_duplicate, stats.analyzed) == (0, 1, 1)
    assert publisher.published == ["Dune: Part Three | Official Trailer"]


def test_clip_is_skipped_before_analysis_and_never_retried(radar) -> None:
    run, publisher = radar
    clip = video("c1", "Dune: Part Three | Movie Clip - The Chase Scene")

    first = run(clip)
    second = run(clip)

    assert (first.skipped_clip, first.analyzed, first.posted) == (1, 0, 0)
    assert second.skipped_existing == 1
    assert publisher.published == []


def test_llm_flagged_clip_with_neutral_title_is_not_published(radar) -> None:
    run, publisher = radar

    def says_clip(candidate, **_kwargs):
        return analysis_from_json(
            candidate,
            {"is_release_signal": True, "release_status": "upcoming", "content_type": "clip"},
        )

    stats = run(video("d1", "Dune: Part Three"), analyze_with=says_clip)

    assert (stats.skipped_clip, stats.posted) == (1, 0)
    assert publisher.published == []


def test_known_item_does_not_hit_the_enricher(radar, monkeypatch, postgres_dsn) -> None:
    run, _ = radar
    run(video("e1", "Dune: Part Three | Official Trailer"))

    def boom(*_args):
        raise AssertionError("yt-dlp nao deve ser chamado para item conhecido")

    monkeypatch.setattr(pipeline, "enrich_candidate", boom)
    assert run(video("e1", "Dune: Part Three | Official Trailer")).skipped_existing == 1


def test_fallback_without_llm_does_not_treat_a_clip_as_a_release() -> None:
    clip = video("f1", "Gameplay Walkthrough - Part 1")
    assert fallback_analysis(clip, "").is_release_signal is False
    trailer = video("f2", "Hollow Knight: Silksong | Gameplay Trailer")
    assert fallback_analysis(trailer, "").is_release_signal is True


def test_dashboard_hides_clips_and_older_duplicates_already_in_the_database(
    postgres_dsn: str,
) -> None:
    init_db(postgres_dsn)
    conn = get_connection(postgres_dsn)
    try:
        rows = [
            video("g1", "Dune: Part Three | Teaser Trailer"),
            video("g2", "Dune: Part Three | Movie Clip"),
            video("g3", "Dune: Part Three | Official Trailer"),
            video("g4", "Outra Obra | Official Trailer"),
        ]
        for index, candidate in enumerate(rows):
            assert reserve_candidate(conn, candidate, f"hash-{index}")
            mark_posted(conn, candidate.external_id)
        # Linha legada: publicada antes de existir work_key.
        with conn.cursor() as cur:
            cur.execute("UPDATE release_items SET work_key = NULL")
        conn.commit()
    finally:
        conn.close()
    init_db(postgres_dsn)  # o backfill preenche as chaves das linhas legadas

    items = list_releases(postgres_dsn)

    assert [item["id"] for item in items] == ["g4", "g3"]
    assert {item["content_type"] for item in items} == {"trailer"}


def test_legacy_clip_never_blocks_the_real_trailer_and_unknown_category_falls_back(
    postgres_dsn: str,
) -> None:
    from release_radar.dedupe import row_work_key

    legacy_clip = {
        "work_key": None,
        "url": "https://www.youtube.com/watch?v=x",
        "source": "youtube",
        "title": "Dune Part Three Trailer REACTION",
        "channel": "Canal",
        "category": "movies",
        "analysis": {"original_title": "Dune: Part Three"},
    }
    assert row_work_key(legacy_clip) == ""

    unknown_category = {
        **legacy_clip,
        "title": "Dune: Part Three | Official Trailer",
        "analysis": {"original_title": "Dune: Part Three", "category": "unknown"},
    }
    assert row_work_key(unknown_category) == "movies:dune part three"


def test_posted_at_is_exposed_with_an_explicit_offset() -> None:
    from datetime import datetime

    from release_radar.web import posted_at_utc

    assert posted_at_utc(datetime(2026, 10, 18, 3, 0)) == "2026-10-18T03:00:00+00:00"
