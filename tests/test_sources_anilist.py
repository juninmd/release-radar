from __future__ import annotations

import json

import httpx

from release_radar.analyzer import source_release_date
from release_radar.links import link_kind
from release_radar.sources.anilist import fetch_anilist, start_date

BODY = {
    "data": {
        "Page": {
            "media": [
                {
                    "id": 198966,
                    "siteUrl": "https://anilist.co/anime/198966",
                    "title": {
                        "romaji": "Dandadan 3rd Season",
                        "english": None,
                        "native": "ダンダダン",
                    },
                    "description": "The third season of <i>Dandadan</i>.<br>Mais um arco.",
                    "startDate": {"year": 2027, "month": None, "day": None},
                    "format": "TV",
                    "episodes": None,
                    "genres": ["Action", "Comedy"],
                    "coverImage": {"extraLarge": "https://img.test/cover.jpg"},
                    "trailer": {"id": "abc123", "site": "youtube"},
                    "studios": {"nodes": [{"name": "Science SARU"}]},
                },
                {
                    "id": 7,
                    "siteUrl": "https://anilist.co/anime/7",
                    "title": {"english": "Com Data"},
                    "startDate": {"year": 2026, "month": 12, "day": 5},
                    "trailer": {"id": "x", "site": "dailymotion"},
                },
                {
                    "id": None,
                    "siteUrl": "https://anilist.co/anime/0",
                    "title": {"english": "Sem id"},
                },
            ]
        }
    }
}


def test_posts_graphql_and_builds_candidates() -> None:
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return httpx.Response(200, json=BODY)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        found = fetch_anilist(client, limit=5)

    assert "NOT_YET_RELEASED" in seen[0]["query"]
    assert seen[0]["variables"] == {"perPage": 5}
    assert [item.external_id for item in found] == ["anilist:198966", "anilist:7"]
    first = found[0]
    assert first.source == "anilist"
    assert first.category == "anime"
    assert first.title == "Dandadan 3rd Season"
    assert first.thumbnail == "https://img.test/cover.jpg"
    assert "The third season of Dandadan.\nMais um arco." in first.description
    assert "Trailer: https://www.youtube.com/watch?v=abc123" in first.description
    assert "Estudio: Science SARU" in first.description


def test_partial_date_is_a_window_not_an_official_release_date() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=BODY))
    with httpx.Client(transport=transport) as client:
        partial, full = fetch_anilist(client, limit=5)

    assert "Janela prevista: 2027" in partial.description
    assert source_release_date(partial) == ""
    assert source_release_date(full) == "2026-12-05"
    assert "Trailer:" not in full.description


def test_start_date_formats() -> None:
    assert start_date({"year": 2026, "month": 3, "day": 9}) == ("2026-03-09", "")
    assert start_date({"year": 2026, "month": 3, "day": None}) == ("", "2026-03")
    assert start_date({"year": None, "month": None, "day": None}) == ("", "")
    assert start_date(None) == ("", "")


def test_catalog_sources_link_to_official_page() -> None:
    for source in ("anilist", "jikan", "tvmaze"):
        assert link_kind("https://example.test/x", source) == "catalog"
