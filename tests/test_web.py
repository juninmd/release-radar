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
