from __future__ import annotations

from datetime import UTC, datetime

import httpx

from release_radar.analyzer import fallback_analysis, source_release_date
from release_radar.sources.tvmaze import fetch_tvmaze


def episode(
    show_id: int,
    name: str,
    airdate: str,
    *,
    season: int = 1,
    number: int = 1,
    kind: str = "regular",
    show_type: str = "Scripted",
    weight: int = 50,
) -> dict:
    return {
        "season": season,
        "number": number,
        "type": kind,
        "airdate": airdate,
        "_embedded": {
            "show": {
                "id": show_id,
                "name": name,
                "url": f"https://www.tvmaze.com/shows/{show_id}",
                "officialSite": f"https://official.test/{show_id}",
                "type": show_type,
                "language": "English",
                "genres": ["Drama"],
                "weight": weight,
                "summary": "<p>Uma <b>serie</b> nova.</p>",
                "webChannel": {"name": "Netflix"},
                "image": {"original": f"https://img.test/{show_id}.jpg"},
            }
        },
    }


def client_for(by_date: dict[str, list[dict]]) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=by_date.get(request.url.params["date"], []))

    return httpx.Client(transport=httpx.MockTransport(handler))


TODAY = datetime(2026, 10, 24, tzinfo=UTC)


def test_only_future_series_premieres_become_candidates() -> None:
    by_date = {
        "2026-10-25": [
            episode(1, "Serie Nova", "2026-10-25"),
            episode(2, "Temporada 2", "2026-10-25", season=2),
            episode(3, "Episodio 2", "2026-10-25", number=2),
            episode(4, "Especial", "2026-10-25", kind="significant_special"),
            episode(5, "Talk Show", "2026-10-25", show_type="Talk Show"),
        ]
    }
    with client_for(by_date) as client:
        found = fetch_tvmaze(client, limit=10, days_ahead=3, today=TODAY)

    assert [item.title for item in found] == ["Serie Nova"]
    item = found[0]
    assert item.external_id == "tvmaze:1"
    assert item.source == "tvmaze"
    assert item.category == "series"
    assert item.url == "https://official.test/1"
    assert item.channel == "Netflix"
    assert item.thumbnail == "https://img.test/1.jpg"
    assert "Uma serie nova." in item.description
    assert "Plataforma: Netflix" in item.description
    assert source_release_date(item) == "2026-10-25"


def test_ranks_by_weight_dedupes_shows_and_applies_limit() -> None:
    by_date = {
        "2026-10-25": [episode(1, "Fraca", "2026-10-25", weight=10)],
        "2026-10-26": [
            episode(2, "Forte", "2026-10-26", weight=90),
            episode(1, "Fraca", "2026-10-26", weight=10),
        ],
        "2026-10-27": [episode(3, "Media", "2026-10-27", weight=50)],
    }
    with client_for(by_date) as client:
        found = fetch_tvmaze(client, limit=2, days_ahead=3, today=TODAY)

    assert [item.title for item in found] == ["Forte", "Media"]


def test_catalog_fallback_marks_premiere_as_upcoming() -> None:
    with client_for({"2026-10-25": [episode(1, "Serie Nova", "2026-10-25")]}) as client:
        item = fetch_tvmaze(client, limit=1, days_ahead=1, today=TODAY)[0]

    analysis = fallback_analysis(item, "")

    assert analysis.is_release_signal
    assert analysis.release_status == "upcoming"
    assert analysis.release_date == "2026-10-25"
