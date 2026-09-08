from __future__ import annotations

import httpx

from release_radar.sources.kitsu import fetch_kitsu

BODY = {
    "data": [
        {
            "id": "48671",
            "attributes": {
                "slug": "witch-on-the-holy-night",
                "canonicalTitle": "Mahoutsukai no Yoru",
                "titles": {"en": "Witch on the Holy Night", "ja_jp": "魔法使いの夜"},
                "synopsis": "Aoko aprende feiticaria.",
                "startDate": "2026-12-01",
                "showType": "movie",
                "episodeCount": 1,
                "youtubeVideoId": "xyz123",
                "posterImage": {"original": "https://media/poster.jpg"},
                "updatedAt": "2026-09-05T12:00:00.000Z",
            },
        },
        {"id": "", "attributes": {"slug": "sem-id"}},
    ]
}


def test_upcoming_anime_becomes_candidate() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=BODY))
    with httpx.Client(transport=transport) as client:
        candidates = fetch_kitsu(client, limit=10)

    assert len(candidates) == 1
    item = candidates[0]
    assert item.external_id == "kitsu:48671"
    assert item.source == "kitsu"
    assert item.category == "anime"
    assert item.title == "Witch on the Holy Night"
    assert item.url == "https://kitsu.io/anime/witch-on-the-holy-night"
    assert item.thumbnail == "https://media/poster.jpg"
    assert item.upload_date == "20260905"


def test_description_exposes_trailer_and_release_window() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=BODY))
    with httpx.Client(transport=transport) as client:
        description = fetch_kitsu(client, limit=10)[0].description

    assert "Estreia prevista: 2026-12-01" in description
    assert "https://www.youtube.com/watch?v=xyz123" in description
    assert "Aoko aprende feiticaria." in description
