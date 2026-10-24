from __future__ import annotations

import httpx

from release_radar.analyzer import source_release_date
from release_radar.sources.jikan import fetch_jikan

BODY = {
    "data": [
        {
            "mal_id": 1,
            "url": "https://myanimelist.net/anime/1",
            "title": "Shingeki",
            "title_english": "Final Anime",
            "title_japanese": "最終",
            "images": {"jpg": {"large_image_url": "https://img.test/1.jpg"}},
            "synopsis": "Uma <b>historia</b> epica.",
            "aired": {"from": "2027-01-10T00:00:00+00:00", "string": "Jan 10, 2027"},
            "type": "TV",
            "episodes": 12,
            "genres": [{"name": "Action"}],
            "studios": [{"name": "MAPPA"}],
            "trailer": {"url": "https://www.youtube.com/watch?v=zzz"},
        },
        {
            "mal_id": 2,
            "url": "https://myanimelist.net/anime/2",
            "title": "Sem Data",
            "aired": {"from": None, "string": "Not available"},
        },
        {
            "mal_id": 1,
            "url": "https://myanimelist.net/anime/1",
            "title": "Duplicado",
        },
        {"mal_id": 3, "title": "Sem url"},
    ]
}


def test_upcoming_season_becomes_candidates() -> None:
    seen: list[httpx.URL] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url)
        return httpx.Response(200, json=BODY)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        found = fetch_jikan(client, limit=10)

    assert seen[0].params["limit"] == "10"
    assert seen[0].params["sfw"] == "true"
    assert [item.external_id for item in found] == ["jikan:1", "jikan:2"]
    first, undated = found
    assert first.source == "jikan"
    assert first.title == "Final Anime"
    assert first.thumbnail == "https://img.test/1.jpg"
    assert "Uma historia epica." in first.description
    assert "Estudio: MAPPA" in first.description
    assert source_release_date(first) == "2027-01-10"
    assert "Estreia prevista" not in undated.description
    assert "Janela prevista" not in undated.description
