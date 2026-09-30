from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from release_radar import pipeline
from release_radar.analyzer import analysis_from_json
from release_radar.config import Settings
from release_radar.db import get_connection, get_item, init_db
from release_radar.models import ReleaseCandidate


@pytest.mark.parametrize(
    ("status", "dry_run", "expected_status", "posted"),
    [
        ("released", False, "skipped", 0),
        ("unknown", False, "skipped", 0),
        ("upcoming", False, "posted", 1),
        ("upcoming", True, None, 0),
    ],
)
def test_publication_policy_persists_and_prevents_delivery(
    postgres_dsn: str,
    monkeypatch,
    status: str,
    dry_run: bool,
    expected_status: str | None,
    posted: int,
) -> None:
    item = ReleaseCandidate(
        external_id="rss:new",
        title="Nova obra",
        url="https://example.test/new",
        channel="Revista",
        category="movies",
        duration=0,
        upload_date=None,
        thumbnail=None,
        source="rss",
    )
    analysis = analysis_from_json(
        item,
        {
            "is_release_signal": True,
            "release_status": status,
            "title": "Nova obra",
        },
    )
    publisher = AsyncMock()
    publisher.publish.return_value = True
    monkeypatch.setattr(pipeline, "init_db", lambda _: init_db(postgres_dsn))
    monkeypatch.setattr(pipeline, "get_connection", lambda _: get_connection(postgres_dsn))
    monkeypatch.setattr(pipeline, "discover", lambda _: [item])
    monkeypatch.setattr(pipeline, "analyze_release", lambda **_: analysis)
    monkeypatch.setattr(pipeline, "TelegramPublisher", lambda *_: publisher)
    settings = Settings(_env_file=None, analyze_video_content=False)

    stats = asyncio.run(pipeline.run_pipeline(settings, dry_run=dry_run))

    assert stats.posted == posted
    assert publisher.publish.await_count == posted
    conn = get_connection(postgres_dsn)
    try:
        row = get_item(conn, item.external_id)
        conn.rollback()
        if expected_status is None:
            assert row is None
            # O teste a seco nao consome o item da proxima rodada real.
            real_stats = asyncio.run(pipeline.run_pipeline(settings))
            assert real_stats.posted == 1
        else:
            assert row is not None
            assert row["status"] == expected_status
            assert row["analysis"]["release_status"] == status
            if status == "released":
                assert row["skipped_reason"] == "Obra ja lancada"
                assert stats.skipped_released == 1
            elif status == "unknown":
                assert row["skipped_reason"] == "Estreia futura nao confirmada"
                assert stats.skipped_unconfirmed == 1
            else:
                repeat = asyncio.run(pipeline.run_pipeline(settings))
                assert repeat.skipped_existing == 1
                assert publisher.publish.await_count == 1
    finally:
        conn.close()
