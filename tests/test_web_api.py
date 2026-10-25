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
        anilist_enabled=False,
        jikan_enabled=False,
        tvmaze_enabled=False,
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


@pytest.fixture
def open_api(postgres_dsn: str) -> Iterator[str]:
    """Sem token e sem permissão explícita: escrita deve ser recusada."""
    init_db(postgres_dsn)
    server = create_server(
        postgres_dsn, port=0, settings=Settings(_env_file=None), allow_anonymous_writes=False
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
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
    started = httpx.post(f"{base}/api/run", json={"dry_run": True}, timeout=5, headers=headers)
    assert started.status_code == 202
    assert started.json()["accepted"] is True

    finished = _await_run(base, headers)
    assert finished["error"] is None
    assert finished["stats"]["discovered"] == 0
    assert finished["stats"]["posted"] == 0
    assert finished["finished_at"] is not None


def test_run_endpoint_rejects_invalid_limit(api) -> None:
    base, headers = api
    response = httpx.post(f"{base}/api/run", json={"limit": 0}, timeout=5, headers=headers)
    assert response.status_code == 400


def test_write_routes_are_refused_when_exposed_without_a_token(open_api: str) -> None:
    assert httpx.get(f"{open_api}/api/releases", timeout=5).status_code == 200
    assert httpx.get(f"{open_api}/api/health", timeout=5).status_code == 200
    blocked = httpx.get(f"{open_api}/api/settings", timeout=5)
    assert blocked.status_code == 403
    assert httpx.post(f"{open_api}/api/run", json={}, timeout=5).status_code == 403
    assert httpx.put(f"{open_api}/api/settings", json={}, timeout=5).status_code == 403


def test_bearer_scheme_is_case_insensitive(api) -> None:
    base, _ = api
    response = httpx.get(
        f"{base}/api/settings", timeout=5, headers={"Authorization": f"bearer {TOKEN}"}
    )
    assert response.status_code == 200


def test_dry_run_requires_a_real_boolean(api) -> None:
    base, headers = api
    for value in ("false", 0, None, 1):
        response = httpx.post(
            f"{base}/api/run", json={"dry_run": value}, timeout=5, headers=headers
        )
        assert response.status_code == 400, value


def test_settings_bound_the_risky_numbers(api) -> None:
    base, headers = api
    for payload in (
        {"max_items_per_run": 10**9},
        {"max_items_per_run": 0},
        {"max_transcription_seconds": 10**9},
        {"rss_limit": True},
        {"rss_limit": 3.9},
        {"rss_limit": "muitos"},
    ):
        response = httpx.put(f"{base}/api/settings", json=payload, timeout=5, headers=headers)
        assert response.status_code == 400, payload


def test_settings_reject_internal_feed_hosts(api) -> None:
    base, headers = api
    for value in (
        "games|http://169.254.169.254/latest/meta-data/",
        "games|http://127.0.0.1:8000/feed",
        "games|http://service.svc.cluster.local:4000/feed",
        "games|ftp://example.test/feed",
        "games|example.test/feed",
    ):
        response = httpx.put(
            f"{base}/api/settings", json={"rss_sources": value}, timeout=5, headers=headers
        )
        assert response.status_code == 400, value

    ok = httpx.put(
        f"{base}/api/settings",
        json={"rss_sources": "games|https://blog.playstation.com/feed/"},
        timeout=5,
        headers=headers,
    )
    assert ok.status_code == 200


def test_settings_are_atomic_when_one_field_is_invalid(api) -> None:
    base, headers = api
    before = httpx.get(f"{base}/api/settings", timeout=5, headers=headers).json()["values"]
    response = httpx.put(
        f"{base}/api/settings",
        json={"rss_limit": before["rss_limit"] + 1, "postgres_password": "vazou"},
        timeout=5,
        headers=headers,
    )
    assert response.status_code == 400
    after = httpx.get(f"{base}/api/settings", timeout=5, headers=headers).json()
    assert after["values"]["rss_limit"] == before["rss_limit"]
    assert "rss_limit" not in after["overridden"]


def test_wrong_method_on_known_route_returns_json_405(api) -> None:
    base, headers = api
    response = httpx.post(f"{base}/api/settings", json={}, timeout=5, headers=headers)
    assert response.status_code == 405
    assert response.json()["error"]
    # Verbos sem handler dedicado tambem respondem JSON, nao o HTML 501 do http.server.
    deleted = httpx.request("DELETE", f"{base}/api/run", timeout=5, headers=headers)
    assert deleted.status_code == 405
    assert deleted.json()["error"]
    assert httpx.post(f"{base}/api/health", json={}, timeout=5).status_code == 405


def test_mutating_routes_require_json_content_type(api) -> None:
    base, headers = api
    # Uma pagina hostil consegue POST "simples" (text/plain): deve ser recusado.
    response = httpx.post(
        f"{base}/api/run",
        content=b'{"dry_run": true}',
        headers={**headers, "Content-Type": "text/plain"},
        timeout=5,
    )
    assert response.status_code == 415
    # Sem corpo tambem: o POST vazio (form/no-cors) nao dispara rodada alguma.
    empty = httpx.post(
        f"{base}/api/run",
        headers={**headers, "Content-Type": "application/x-www-form-urlencoded"},
        timeout=5,
    )
    assert empty.status_code == 415
    assert httpx.post(f"{base}/api/run", headers=headers, timeout=5).status_code == 415


def test_run_limit_respects_the_same_bounds(api) -> None:
    base, headers = api
    for value in (True, 3.9, 0, 10**6):
        response = httpx.post(f"{base}/api/run", json={"limit": value}, timeout=5, headers=headers)
        assert response.status_code == 400, value


@pytest.fixture
def anon_api(postgres_dsn: str) -> Iterator[tuple[str, int]]:
    init_db(postgres_dsn)
    settings = Settings(_env_file=None)
    server = create_server(postgres_dsn, port=0, settings=settings, allow_anonymous_writes=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", server.server_port
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def test_put_settings_rejects_untrusted_host_without_token(anon_api) -> None:
    base, port = anon_api
    blocked = httpx.put(
        f"{base}/api/settings",
        json={"rss_limit": 7},
        headers={"Host": "evil.example:8765"},
        timeout=5,
    )
    assert blocked.status_code == 421
    assert blocked.json() == {"error": "Host nao permitido."}

    allowed = httpx.put(
        f"{base}/api/settings",
        json={"rss_limit": 7},
        headers={"Host": f"127.0.0.1:{port}"},
        timeout=5,
    )
    assert allowed.status_code == 200


def test_post_run_rejects_untrusted_origin(anon_api) -> None:
    base, port = anon_api
    blocked = httpx.post(
        f"{base}/api/run",
        json={"dry_run": True},
        headers={"Host": f"127.0.0.1:{port}", "Origin": "http://evil.example"},
        timeout=5,
    )
    assert blocked.status_code == 421
    assert blocked.json() == {"error": "Host nao permitido."}


def test_public_routes_allow_any_host(anon_api) -> None:
    base, _ = anon_api
    evil_headers = {"Host": "rebind.example.test:8765"}
    assert httpx.get(f"{base}/healthz", headers=evil_headers, timeout=5).status_code == 200
    assert httpx.get(f"{base}/api/health", headers=evil_headers, timeout=5).status_code == 200
    assert httpx.get(f"{base}/api/releases", headers=evil_headers, timeout=5).status_code == 200


def test_release_radar_allowed_hosts_setting(postgres_dsn: str) -> None:
    init_db(postgres_dsn)
    settings = Settings(
        _env_file=None, release_radar_allowed_hosts="panel.example.test, custom.local"
    )
    server = create_server(postgres_dsn, port=0, settings=settings, allow_anonymous_writes=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        response = httpx.put(
            f"{base}/api/settings",
            json={"rss_limit": 7},
            headers={"Host": "panel.example.test:8765"},
            timeout=5,
        )
        assert response.status_code == 200

        origin_ok = httpx.post(
            f"{base}/api/run",
            json={"dry_run": True},
            headers={
                "Host": f"127.0.0.1:{server.server_port}",
                "Origin": "https://custom.local:8765",
            },
            timeout=5,
        )
        assert origin_ok.status_code == 202
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def test_valid_token_bypasses_host_check(api) -> None:
    base, headers = api
    # Com token valido em Authorization header, Host estranho e aceito.
    response = httpx.put(
        f"{base}/api/settings",
        json={"rss_limit": 7},
        headers={**headers, "Host": "evil.example:8765"},
        timeout=5,
    )
    assert response.status_code == 200
