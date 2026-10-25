from __future__ import annotations

import threading
from collections.abc import Iterator

import httpx
import pytest

from release_radar.analyzer import analysis_from_json
from release_radar.db import get_connection, init_db, mark_posted, reserve_candidate, save_analysis
from release_radar.models import ReleaseCandidate
from release_radar.web import create_server


@pytest.fixture
def web_url(postgres_dsn: str) -> Iterator[str]:
    init_db(postgres_dsn)
    conn = get_connection(postgres_dsn)
    try:
        for source in ("youtube", "rss", "steam", "kitsu"):
            url = (
                "https://youtu.be/demo" if source == "youtube" else f"https://example.test/{source}"
            )
            candidate = ReleaseCandidate(
                external_id=source,
                title=source,
                url=url,
                channel=source,
                category="games",
                duration=0,
                upload_date=None,
                thumbnail=None,
                source=source,
            )
            assert reserve_candidate(conn, candidate, source)
            analysis = analysis_from_json(
                candidate,
                {
                    "title": f"Obra {source}",
                    "is_release_signal": True,
                    "release_status": "upcoming",
                    "synopsis": "Sinopse de teste",
                },
            )
            save_analysis(conn, candidate, "", analysis)
            # Kitsu ainda nao publicado: nao deve aparecer no feed publico.
            if source != "kitsu":
                mark_posted(conn, candidate.external_id)
    finally:
        conn.close()
    server = create_server(postgres_dsn, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def test_http_api_only_exposes_published_items_and_separates_destinations(web_url: str) -> None:
    response = httpx.get(f"{web_url}/api/releases", timeout=5)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    items = response.json()["items"]
    assert [item["kind"] for item in items] == ["catalog", "article", "video"]
    # Titulo neutro nao prova que e trailer: o painel nao inventa o rotulo.
    assert [item["content_type"] for item in items] == ["catalog", "article", "video"]
    assert {item["title"] for item in items} == {"Obra youtube", "Obra rss", "Obra steam"}
    assert all(item["summary"] == "Sinopse de teste" for item in items)
    assert not any("transcript" in item or "raw" in item for item in items)


def test_server_serves_bundled_frontend_and_rejects_unknown_paths(web_url: str) -> None:
    response = httpx.get(web_url, timeout=5)
    assert response.status_code == 200
    assert 'lang="pt-BR"' in response.text
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert httpx.get(f"{web_url}/app.js", timeout=5).status_code == 200
    assert httpx.get(f"{web_url}/app.css", timeout=5).status_code == 200
    assert httpx.get(f"{web_url}/.env", timeout=5).status_code == 404


def test_database_failure_returns_generic_error_without_connection_details(
    web_url: str,
    monkeypatch,
) -> None:
    from release_radar import web

    def fail(_dsn):
        raise RuntimeError("private-connection-details")

    monkeypatch.setattr(web, "list_releases", fail)
    response = httpx.get(f"{web_url}/api/releases", timeout=5)
    assert response.status_code == 503
    assert response.json() == {"error": "Nao foi possivel carregar os lancamentos."}
    assert "private-connection-details" not in response.text


def test_static_files_use_etag_and_answer_304_when_unchanged(web_url: str) -> None:
    first = httpx.get(f"{web_url}/app.js", timeout=5)
    etag = first.headers["etag"]
    assert first.headers["cache-control"] == "no-cache"

    again = httpx.get(f"{web_url}/app.js", headers={"If-None-Match": etag}, timeout=5)

    assert again.status_code == 304
    assert again.content == b""
    assert again.headers["etag"] == etag
    assert httpx.get(f"{web_url}/app.js", headers={"If-None-Match": '"outro"'}).status_code == 200


def test_healthz_checks_the_database(web_url: str) -> None:
    response = httpx.get(f"{web_url}/healthz", timeout=5)
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["cache-control"] == "no-store"


def test_api_rate_limit_returns_429_with_retry_after(postgres_dsn: str) -> None:
    init_db(postgres_dsn)
    server = create_server(postgres_dsn, port=0, rate_burst=2, rate_per_second=0.1)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_port}/api/releases"
        statuses = [httpx.get(url, timeout=5).status_code for _ in range(3)]
        limited = httpx.get(url, timeout=5)
        assert statuses == [200, 200, 429]
        assert limited.status_code == 429
        assert int(limited.headers["retry-after"]) >= 1
        # Arquivos estaticos e health check nao entram na cota da API.
        assert httpx.get(url.replace("/api/releases", "/healthz"), timeout=5).status_code == 200
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def test_api_responses_are_cached_between_requests(
    postgres_dsn: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from release_radar import web

    init_db(postgres_dsn)
    calls = []
    real = web.list_releases
    monkeypatch.setattr(web, "list_releases", lambda *a, **k: calls.append(1) or real(*a, **k))
    server = create_server(postgres_dsn, port=0, cache_ttl=60)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_port}/api/releases"
        bodies = {httpx.get(url, timeout=5).text for _ in range(5)}
        assert len(bodies) == 1
        assert len(calls) == 1
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def test_slowloris_socket_timeout_closes_connection(postgres_dsn: str) -> None:
    import socket
    import time

    init_db(postgres_dsn)
    socket_timeout = 0.2
    server = create_server(
        postgres_dsn, port=0, allow_anonymous_writes=True, socket_timeout=socket_timeout
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        start_time = time.monotonic()
        s = socket.create_connection(("127.0.0.1", server.server_port))
        s.sendall(
            b"PUT /api/settings HTTP/1.1\r\n"
            b"Host: 127.0.0.1\r\n"
            b"Content-Type: application/json\r\n"
            b"Content-Length: 60000\r\n\r\n{"
        )
        s.settimeout(2.0)
        response = b""
        try:
            while True:
                chunk = s.recv(4096)
                if not chunk:
                    break
                response += chunk
        except (TimeoutError, OSError):
            pass
        s.close()
        elapsed = time.monotonic() - start_time
        assert elapsed < socket_timeout + 1.0
        assert b"408" in response
        assert b"Tempo limite excedido" in response
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def test_list_releases_keeps_reading_until_hidden_clips_are_replaced(
    postgres_dsn: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from release_radar import web

    init_db(postgres_dsn)
    conn = get_connection(postgres_dsn)
    try:
        # 3 artigos antigos atras de 6 clipes recentes: um lote fixo de 4 nao os alcancaria.
        for index in range(9):
            clip = index >= 3
            candidate = ReleaseCandidate(
                external_id=f"item{index}",
                title=f"Behind the scenes {index}" if clip else f"Artigo {index}",
                url=f"https://youtu.be/clip{index}" if clip else f"https://example.test/{index}",
                channel="canal",
                category="movies",
                duration=0,
                upload_date=None,
                thumbnail=None,
                source="youtube" if clip else "rss",
            )
            assert reserve_candidate(conn, candidate, f"hash{index}")
            mark_posted(conn, candidate.external_id)
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE release_items SET posted_at = '2026-01-01'::timestamp "
                    "+ %s * interval '1 hour' WHERE external_id = %s",
                    (-index if not clip else index, candidate.external_id),
                )
        conn.commit()
    finally:
        conn.close()
    monkeypatch.setattr(web, "BATCH_SIZE", 2)

    items = web.list_releases(postgres_dsn, limit=3)

    assert [item["id"] for item in items] == ["item0", "item1", "item2"]
    assert all(item["kind"] == "article" for item in items)
