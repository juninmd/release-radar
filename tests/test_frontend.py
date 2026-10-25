"""Execute com `uv run --with playwright pytest tests/test_frontend.py`.

O navegador exercita HTML/CSS/JS reais; a API fornece dados ficticios isolados.
"""

from __future__ import annotations

import os
import threading
from collections.abc import Iterator
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from release_radar.web import create_server

playwright = pytest.importorskip("playwright.sync_api", reason="requer Playwright para navegador")
expect = playwright.expect

ITEMS = [
    {
        "id": "video",
        "title": "Fronteira de Órion",
        "kind": "video",
        "content_type": "trailer",
        "source": "youtube",
        "url": "https://youtu.be/demo",
        "category": "movies",
        "channel": "Cinema em foco",
        "summary": "Uma missão encontra sinais de vida no limite de um sistema desconhecido.",
        "release_window": "Novembro de 2026",
        "availability": "upcoming",
        "platforms": ["Cinema"],
        "why_it_matters": "Uma aventura de ficção científica para acompanhar.",
        "thumbnail": "https://preview.example/orion",
    },
    {
        "id": "article",
        "title": "Maré Alta: uma nova temporada",
        "kind": "article",
        "source": "rss",
        "url": "https://example.test/article",
        "category": "series",
        "channel": "Diário de estreias",
        "summary": "A próxima temporada explora os segredos de uma pequena comunidade costeira.",
        "release_window": "Setembro de 2026",
        "availability": "released",
        "thumbnail": "https://preview.example/mare",
    },
    {
        "id": "game",
        "title": "A Última Cidade",
        "kind": "catalog",
        "source": "steam",
        "url": "https://store.steampowered.com/app/123",
        "category": "games",
        "channel": "Steam",
        "summary": "Construa um lar e escolha o destino de uma civilização em um mundo em ruínas.",
        "release_window": "Dezembro de 2026",
        "availability": "upcoming",
        "thumbnail": "https://preview.example/cidade",
    },
    {
        "id": "anime",
        "title": "Jardim das Estrelas",
        "kind": "catalog",
        "source": "kitsu",
        "url": "https://kitsu.io/anime/demo",
        "category": "anime",
        "channel": "Kitsu",
        "summary": "Dois amigos buscam um jardim que só aparece à noite.",
        "release_window": "2027",
        "availability": "unconfirmed",
        "thumbnail": None,
    },
]


@pytest.fixture(scope="module")
def app_url() -> Iterator[str]:
    server = create_server("", port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


@pytest.fixture
def page():
    with playwright.sync_playwright() as runtime:
        executable = os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE")
        browser = runtime.chromium.launch(executable_path=executable or None)
        context = browser.new_context(
            viewport={"width": 1440, "height": 1000}, reduced_motion="reduce"
        )
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        colors = {
            "orion": ("#294450", "#e8ad78"),
            "mare": ("#185863", "#a7d5cc"),
            "cidade": ("#4a4b31", "#b9e87b"),
        }

        def artwork(route):
            name = route.request.url.rsplit("/", 1)[-1]
            background, foreground = colors[name]
            svg = (
                f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 720 360">'
                f'<rect width="720" height="360" fill="{background}"/>'
                f'<circle cx="530" cy="140" r="110" fill="{foreground}"/>'
                '<path d="M0 360V260L160 135L310 275L460 200L720 340V360Z" '
                'fill="#14242b"/><path d="M0 360V310L270 245L430 300L720 255V360Z" '
                'fill="#101921"/></svg>'
            )
            route.fulfill(content_type="image/svg+xml", body=svg)

        page.route("https://preview.example/**", artwork)
        yield page
        assert not errors, errors
        context.close()
        browser.close()


def load(page, app_url: str, items: list[dict] = ITEMS) -> None:
    page.route("**/api/releases", lambda route: route.fulfill(json={"items": items}))
    page.goto(app_url)
    expect(page.locator(".card")).to_have_count(len(items))


def test_link_and_category_filters_search_and_empty_results(page, app_url: str) -> None:
    load(page, app_url)
    page.get_by_role("button", name="YouTube").click()
    expect(page.locator(".card")).to_have_count(1)
    expect(page.get_by_role("heading", name="Fronteira de Órion")).to_be_visible()
    page.get_by_role("button", name="Artigos").click()
    expect(page.locator(".card")).to_have_count(1)
    expect(page.get_by_role("heading", name="Maré Alta: uma nova temporada")).to_be_visible()
    page.get_by_role("button", name="Páginas oficiais").click()
    expect(page.locator(".card")).to_have_count(2)
    page.get_by_label("Categoria").select_option("anime")
    expect(page.locator(".card")).to_have_count(1)
    page.get_by_role("button", name="Todos").click()
    page.get_by_label("Categoria").select_option("all")
    page.get_by_role("searchbox").fill("Cinema")
    expect(page.locator(".card")).to_have_count(1)
    page.get_by_role("searchbox").fill("sem resultados")
    expect(page.locator(".card")).to_have_count(0)
    expect(page.get_by_role("status")).to_contain_text("Nada por aqui")
    page.get_by_role("button", name="Limpar filtros").click()
    expect(page.locator(".card")).to_have_count(4)
    page.get_by_label("Disponibilidade").select_option("upcoming")
    expect(page.locator(".card")).to_have_count(2)
    page.get_by_label("Disponibilidade").select_option("released")
    expect(page.locator(".card")).to_have_count(1)
    page.get_by_role("button", name="Limpar filtros").click()
    page.get_by_role("searchbox").fill("Orion")
    expect(page.locator(".card")).to_have_count(1)
    page.locator(".card-details summary").click()
    expect(page.get_by_role("heading", name="Onde assistir ou jogar")).to_be_visible()


def test_desktop_mobile_and_keyboard_navigation(page, app_url: str, tmp_path: Path) -> None:
    load(page, app_url)
    screenshots = Path(os.environ.get("RELEASE_RADAR_SCREENSHOT_DIR", str(tmp_path)))
    screenshots.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(screenshots / "desktop.png"), full_page=True)
    page.keyboard.press("Tab")
    expect(page.locator(".brand")).to_be_focused()
    page.keyboard.press("Tab")
    expect(page.get_by_role("button", name="Todos")).to_be_focused()
    page.set_viewport_size({"width": 390, "height": 844})
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    expect(page.get_by_role("searchbox")).to_be_visible()
    page.screenshot(path=str(screenshots / "mobile.png"), full_page=True)


def test_loading_empty_and_api_failure_states(page, app_url: str, tmp_path: Path) -> None:
    screenshots = Path(os.environ.get("RELEASE_RADAR_SCREENSHOT_DIR", str(tmp_path)))
    screenshots.mkdir(parents=True, exist_ok=True)
    pending = []
    page.route("**/api/releases", lambda route: pending.append(route))
    page.goto(app_url)
    expect(page.get_by_role("status")).to_contain_text("Buscando novidades")
    expect(page.locator("#result-count")).to_contain_text("Carregando")
    assert pending
    page.screenshot(path=str(screenshots / "loading.png"), full_page=True)
    pending[0].fulfill(json={"items": []})
    expect(page.get_by_role("status")).to_contain_text("Ainda não há")
    page.screenshot(path=str(screenshots / "empty.png"), full_page=True)
    page.unroute("**/api/releases")
    page.route(
        "**/api/releases", lambda route: route.fulfill(status=503, json={"error": "offline"})
    )
    page.reload()
    expect(page.get_by_role("status")).to_contain_text("Não foi possível carregar")
    page.screenshot(path=str(screenshots / "error.png"), full_page=True)
    page.unroute("**/api/releases")
    page.route("**/api/releases", lambda route: route.fulfill(json={"items": ITEMS}))
    page.get_by_role("button", name="Tentar novamente").click()
    expect(page.locator(".card")).to_have_count(4)


def test_untrusted_titles_and_urls_cannot_inject_markup(page, app_url: str) -> None:
    item = {
        **ITEMS[0],
        "title": '<img src=x onerror="window.injected=true">',
        "url": "javascript:window.injected=true",
        "thumbnail": None,
    }
    load(page, app_url, [item])
    expect(page.locator(".card h3")).to_have_text(item["title"])
    expect(page.locator(".card h3 img")).to_have_count(0)
    assert not page.evaluate("Boolean(window.injected)")
    expect(page.locator("a.card-link")).to_have_count(0)
    expect(page.locator(".card-link")).to_have_text("Link indisponível")


def test_video_badge_tells_trailers_apart_and_flags_fresh_posts(page, app_url: str) -> None:
    fresh = datetime.now().isoformat()
    stale = (datetime.now() - timedelta(days=10)).isoformat()
    items = [
        {**ITEMS[0], "content_type": "teaser", "posted_at": fresh},
        {**ITEMS[1], "id": "old", "kind": "video", "content_type": "trailer", "posted_at": stale},
        {**ITEMS[2], "id": "legacy", "kind": "video", "content_type": "video"},
    ]
    load(page, app_url, items)
    badges = page.locator(".thumb .kind").all_text_contents()
    assert badges == ["Teaser", "Trailer", "Vídeo"]
    expect(page.get_by_role("link", name="Assistir teaser: Fronteira de Órion")).to_be_visible()
    expect(
        page.get_by_role("link", name="Assistir trailer: Maré Alta: uma nova temporada")
    ).to_be_visible()
    expect(page.get_by_role("link", name="Assistir: A Última Cidade")).to_be_visible()
    expect(page.locator(".fresh")).to_have_count(1)
    expect(page.locator(".card").first.locator(".fresh")).to_have_text("Novo")


def test_sort_by_nearest_premiere_puts_dated_upcoming_first_and_resets(page, app_url: str) -> None:
    items = [
        {**ITEMS[0], "id": "far", "title": "Distante", "release_date": "2027-03-01"},
        {**ITEMS[1], "id": "done", "title": "Lançada"},
        {**ITEMS[2], "id": "near", "title": "Próxima", "release_date": "2026-11-15"},
    ]
    load(page, app_url, items)
    titles = page.locator(".card h3")
    assert titles.all_inner_texts() == ["Distante", "Lançada", "Próxima"]
    page.get_by_label("Ordenar").select_option("soon")
    assert titles.all_inner_texts() == ["Próxima", "Distante", "Lançada"]
    page.get_by_role("button", name="Limpar filtros").click()
    assert titles.all_inner_texts() == ["Distante", "Lançada", "Próxima"]


def test_search_debounce_and_reset_focus(page, app_url: str) -> None:
    load(page, app_url)
    search_box = page.get_by_role("searchbox")
    search_box.focus()
    search_box.type("Orion", delay=20)  # Total ~100ms (< 200ms)
    # Immediately after typing, before 200ms debounce completes, all 4 cards still visible
    expect(page.locator(".card")).to_have_count(4)
    # After 250ms, debounced search filters to 1 card
    page.wait_for_timeout(250)
    expect(page.locator(".card")).to_have_count(1)

    # Click reset filters button
    page.get_by_role("button", name="Limpar filtros").click()
    expect(page.locator("#result-count")).to_be_focused()
    expect(page.locator(".card")).to_have_count(4)


def test_details_open_state_preserved_when_filters_change(page, app_url: str) -> None:
    load(page, app_url)
    first_details = page.locator(".card-details").first
    first_details.locator("summary").click()
    expect(first_details).to_have_attribute("open", "")

    # Change category filter to 'movies' which retains the first card (Fronteira de Órion)
    page.get_by_label("Categoria").select_option("movies")
    expect(page.locator(".card")).to_have_count(1)
    expect(page.locator(".card-details").first).to_have_attribute("open", "")


def test_accessibility_live_regions_and_axe_audit(page, app_url: str) -> None:
    load(page, app_url)
    # Check live region attributes
    expect(page.locator("#cards")).not_to_have_attribute("aria-live", "")
    expect(page.locator("#result-count")).to_have_attribute("aria-live", "polite")
    expect(page.locator("#result-count")).to_have_attribute("aria-atomic", "true")

    # Run axe-core audit using page.evaluate with script source
    axe_path = Path("frontend/node_modules/axe-core/axe.min.js")
    if axe_path.exists():
        axe_script = axe_path.read_text("utf-8")
        results = page.evaluate(f"() => {{ {axe_script}; return axe.run(); }}")
        violations = results.get("violations", [])
        assert len(violations) == 0, f"Axe accessibility violations found: {violations}"
