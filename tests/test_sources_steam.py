from __future__ import annotations

import json

import httpx

from release_radar.sources.steam import fetch_steam

SEARCH_BODY = {
    "items": [
        {
            "name": "Halloween: The Game",
            "logo": "https://cdn/store_item_assets/steam/apps/3219630/abc/capsule_sm_120.jpg",
        },
        {"name": "Jogo lancado", "logo": "https://cdn/apps/111/x/capsule_sm_120.jpg"},
        {"name": "DLC qualquer", "logo": "https://cdn/apps/222/x/capsule_sm_120.jpg"},
        {"name": "Sem id", "logo": "https://cdn/sem-padrao.jpg"},
    ]
}

DETAILS = {
    "3219630": {
        "success": True,
        "data": {
            "type": "game",
            "name": "Halloween: The Game",
            "short_description": "Torna-te o &quot;bicho-papao&quot;.",
            "release_date": {"coming_soon": True, "date": "8 set. 2026"},
            "genres": [{"description": "Acao"}],
            "developers": ["IllFonic"],
            "publishers": ["IllFonic Publishing"],
            "header_image": "https://cdn/header.jpg",
            "movies": [{"id": 1}],
        },
    },
    "111": {
        "success": True,
        "data": {
            "type": "game",
            "name": "Jogo lancado",
            "release_date": {"coming_soon": False, "date": "1 jan. 2020"},
        },
    },
    "222": {
        "success": True,
        "data": {"type": "dlc", "name": "DLC", "release_date": {"coming_soon": True}},
    },
}


def handler(request: httpx.Request) -> httpx.Response:
    if request.url.path.startswith("/search"):
        return httpx.Response(200, json=SEARCH_BODY)
    app_id = request.url.params["appids"]
    return httpx.Response(200, text=json.dumps({app_id: DETAILS[app_id]}))


def test_only_upcoming_games_become_candidates() -> None:
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        candidates = fetch_steam(client, limit=5)

    assert len(candidates) == 1
    item = candidates[0]
    assert item.external_id == "steam:3219630"
    assert item.source == "steam"
    assert item.category == "games"
    assert item.url == "https://store.steampowered.com/app/3219630/"
    assert item.thumbnail == "https://cdn/header.jpg"
    assert item.duration == 0


def test_description_carries_release_window_and_unescapes_html() -> None:
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        description = fetch_steam(client, limit=5)[0].description

    assert '"bicho-papao"' in description
    assert "Lancamento previsto: 8 set. 2026" in description
    assert "Generos: Acao" in description
    assert "Plataforma: PC (Steam)" in description


def test_limit_stops_detail_requests() -> None:
    calls: list[str] = []

    def counting(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return handler(request)

    with httpx.Client(transport=httpx.MockTransport(counting)) as client:
        assert len(fetch_steam(client, limit=1)) == 1

    # Para no primeiro candidato valido em vez de detalhar a busca inteira.
    assert len([path for path in calls if "appdetails" in path]) == 1
