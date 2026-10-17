from __future__ import annotations

import pytest

from release_radar.config import Settings
from release_radar.settings_store import (
    EDITABLE_FIELDS,
    coerce,
    effective_settings,
    public_settings,
    validate,
)


def _settings(**overrides) -> Settings:
    return Settings(_env_file=None, **overrides)


def test_editable_fields_never_include_secrets() -> None:
    forbidden = {"telegram_bot_token", "llm_api_key", "postgres_password", "postgres_dsn"}
    assert forbidden.isdisjoint(EDITABLE_FIELDS)


@pytest.mark.parametrize(
    ("value", "expected"),
    [(True, True), ("true", True), ("1", True), ("sim", True), ("nao", False), ("", False)],
)
def test_coerce_accepts_common_boolean_spellings(value, expected) -> None:
    assert coerce("steam_enabled", value) is expected


def test_coerce_rejects_unknown_boolean_and_negative_integers() -> None:
    with pytest.raises(ValueError):
        coerce("steam_enabled", "talvez")
    with pytest.raises(ValueError):
        coerce("rss_limit", -1)
    with pytest.raises(ValueError):
        coerce("rss_limit", "muitos")


def test_coerce_rejects_booleans_and_floats_for_numbers() -> None:
    with pytest.raises(ValueError):
        coerce("rss_limit", True)
    with pytest.raises(ValueError):
        coerce("rss_limit", 3.9)


def test_coerce_bounds_the_expensive_limits() -> None:
    for value in (0, 10**9):
        with pytest.raises(ValueError):
            coerce("max_items_per_run", value)
    with pytest.raises(ValueError):
        coerce("rss_limit", 51)
    with pytest.raises(ValueError):
        coerce("max_transcription_seconds", 10**9)
    assert coerce("max_items_per_run", 25) == 25


@pytest.mark.parametrize(
    "value",
    [
        "games|http://169.254.169.254/x",
        "games|http://10.0.0.5/feed",
        "games|http://localhost/feed",
        "games|http://db.internal/feed",
        "games|https://service.svc.cluster.local/feed",
        "games|ftp://example.test/feed",
        "games|example.test/feed",
    ],
)
def test_coerce_rejects_internal_or_non_http_feeds(value: str) -> None:
    with pytest.raises(ValueError):
        coerce("rss_sources", value)


def test_coerce_accepts_public_feeds_and_empty_list() -> None:
    assert coerce("rss_sources", "games|https://blog.playstation.com/feed/").startswith("games|")
    assert coerce("rss_sources", "  ") == ""
    assert coerce("youtube_sources", "games|@PlayStation") == "games|@PlayStation"


def test_validate_rejects_unknown_fields() -> None:
    with pytest.raises(ValueError, match="desconhecidos"):
        validate({"youtube_sources": "", "telegram_bot_token": "vazou"})


def test_effective_settings_applies_only_known_overrides() -> None:
    base = _settings(source_limit=10, rss_limit=5)
    result = effective_settings(base, {"source_limit": 3, "postgres_password": "hack"})
    assert result.source_limit == 3
    assert result.rss_limit == 5
    assert result.postgres_password == base.postgres_password


def test_public_settings_hides_secrets_and_marks_overrides() -> None:
    base = _settings(llm_api_key="segredo", source_limit=10)
    payload = public_settings(base, {"source_limit": 4})
    assert payload["values"]["source_limit"] == 4
    assert payload["overridden"] == ["source_limit"]
    assert "llm_api_key" not in payload["values"]
    assert "segredo" not in str(payload)
