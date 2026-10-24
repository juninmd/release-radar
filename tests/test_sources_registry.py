from __future__ import annotations

from release_radar.config import Settings
from release_radar.models import ReleaseCandidate
from release_radar.sources import discover_extra_sources


def base_settings(**overrides: object) -> Settings:
    defaults: dict[str, object] = {
        "steam_enabled": False,
        "kitsu_enabled": False,
        "anilist_enabled": False,
        "jikan_enabled": False,
        "tvmaze_enabled": False,
        "rss_sources": "",
    }
    defaults.update(overrides)
    return Settings(**defaults)  # type: ignore[arg-type]


def test_all_extra_sources_disabled_skips_http() -> None:
    assert discover_extra_sources(base_settings()) == []


def test_failing_source_does_not_abort_the_others(monkeypatch) -> None:
    import release_radar.sources as sources

    def boom(*args: object, **kwargs: object) -> list[ReleaseCandidate]:
        raise RuntimeError("steam fora do ar")

    survivor = ReleaseCandidate(
        external_id="kitsu:1",
        title="Anime",
        url="https://kitsu.io/anime/x",
        channel="Kitsu",
        category="anime",
        duration=0,
        upload_date="20260907",
        thumbnail=None,
        source="kitsu",
    )
    monkeypatch.setattr(sources, "fetch_steam", boom)
    monkeypatch.setattr(sources, "fetch_kitsu", lambda *a, **k: [survivor])

    found = discover_extra_sources(base_settings(steam_enabled=True, kitsu_enabled=True))

    assert [item.source for item in found] == ["kitsu"]


def test_parsed_rss_sources_pairs_category_and_url() -> None:
    settings = base_settings(rss_sources="games|https://a/feed, anime|https://b/feed")
    assert settings.parsed_rss_sources == [
        ("games", "https://a/feed"),
        ("anime", "https://b/feed"),
    ]


def test_sources_run_in_parallel_and_keep_registration_order(monkeypatch) -> None:
    import threading

    import release_radar.sources as sources

    barrier = threading.Barrier(2, timeout=5)

    def make(name: str):
        def fetch(*args: object, **kwargs: object) -> list[ReleaseCandidate]:
            # Se rodassem em sequencia, a segunda nunca chegaria na barreira.
            barrier.wait()
            return [
                ReleaseCandidate(
                    external_id=f"{name}:1",
                    title=name,
                    url=f"https://{name}.test/1",
                    channel=name,
                    category="anime",
                    duration=0,
                    upload_date=None,
                    thumbnail=None,
                    source=name,
                )
            ]

        return fetch

    monkeypatch.setattr(sources, "fetch_steam", make("steam"))
    monkeypatch.setattr(sources, "fetch_kitsu", make("kitsu"))

    found = discover_extra_sources(base_settings(steam_enabled=True, kitsu_enabled=True))

    assert [item.source for item in found] == ["steam", "kitsu"]


def test_failures_are_reported_per_source(monkeypatch) -> None:
    import release_radar.sources as sources

    def boom(*args: object, **kwargs: object) -> list[ReleaseCandidate]:
        raise RuntimeError("anilist fora do ar")

    errors: list[str] = []
    monkeypatch.setattr(sources, "fetch_anilist", boom)

    found = discover_extra_sources(
        base_settings(anilist_enabled=True), lambda name, exc: errors.append(name)
    )

    assert found == []
    assert errors == ["anilist"]
