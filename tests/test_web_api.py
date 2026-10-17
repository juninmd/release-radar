from __future__ import annotations

import threading
import time
from collections.abc import Iterator

import httpx
import pytest

from release_radar.config import Settings
from release_radar.db import init_db
from release_radar.web import create_server

TOKEN = "s3cret-token"


@pytest.fixture
def api(postgres_dsn: str) -> Iterator[tuple[str, dict]]:
    init_db(postgres_dsn)
    settings = Settings(
        _env_file=None,
        youtube_sources="",
        rss_sources="",
        steam_enabled=False,
        kitsu_enabled=False,
        telegram_bot_token="",
        telegram_chat_id="",
        llm_api_key="",
    )
    server = create_server(postgres_dsn, port=0, settings=settings, token=TOKEN)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", {"Authorization": f"Bearer {TOKEN}"}
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def test_health_and_releases_stay_open_when_a_token_is_configured(api) -> None:
    base, _ = api
    assert httpx.get(f"{base}/api/health", timeout=5).json()["status"] == "ok"
    assert httpx.get(f"{base}/api/releases", timeout=5).status_code == 200


def test_settings_and_run_require_the_token(api) -> None:
    base, _ = api
    assert httpx.get(f"{base}/api/settings", timeout=5).status_code == 401
    assert httpx.post(f"{base}/api/run", json={}, timeout=5).status_code == 401
    assert httpx.get(f"{base}/api/run", timeout=5).status_code == 401


def test_settings_roundtrip_persists_only_whitelisted_fields(api) -> None:
    base, headers = api
    response = httpx.get(f"{base}/api/settings", timeout=5, headers=headers)
    assert response.status_code == 200
    assert response.json()["values"]["steam_enabled"] is False

    saved = httpx.put(
        f"{base}/api/settings",
        json={"steam_enabled": True, "rss_limit": 7},
        timeout=5,
        headers=headers,
    )
    assert saved.status_code == 200
    assert saved.json()["saved"] == ["rss_limit", "steam_enabled"]
    assert saved.json()["overridden"] == ["rss_limit", "steam_enabled"]

    reread = httpx.get(f"{base}/api/settings", timeout=5, headers=headers).json()
    assert reread["values"]["steam_enabled"] is True
    assert reread["values"]["rss_limit"] == 7


def test_settings_rejects_unknown_fields(api) -> None:
    base, headers = api
    response = httpx.put(
        f"{base}/api/settings", json={"postgres_password": "x"}, timeout=5, headers=headers
    )
    assert response.status_code == 400
    assert "desconhecidos" in response.json()["error"]


def _await_run(base: str, headers: dict, timeout: float = 10.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        payload = httpx.get(f"{base}/api/run", timeout=5, headers=headers).json()
        if not payload["running"]:
            return payload
        time.sleep(0.05)
    raise AssertionError("a rodada nao terminou a tempo")


def test_run_endpoint_runs_the_pipeline_and_reports_stats(api) -> None:
    base, headers = api
    started = httpx.post(
        f"{base}/api/run", json={"dry_run": True}, timeout=5, headers=headers
    )
    assert started.status_code == 202
    assert started.json()["accepted"] is True

    finished = _await_run(base, headers)
    assert finished["error"] is None
    assert finished["stats"]["discovered"] == 0
    assert finished["stats"]["posted"] == 0
    assert finished["finished_at"] is not None


def test_run_endpoint_rejects_invalid_limit(api) -> None:
    base, headers = api
    response = httpx.post(
        f"{base}/api/run", json={"limit": 0}, timeout=5, headers=headers
    )
    assert response.status_code == 400
