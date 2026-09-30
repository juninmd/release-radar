from datetime import date

from release_radar.analyzer import analysis_from_json, fallback_analysis
from release_radar.models import ReleaseCandidate
from release_radar.pipeline import already_released, confirmed_upcoming


def candidate(source: str = "youtube", description: str = "") -> ReleaseCandidate:
    return ReleaseCandidate(
        external_id="test",
        title="Nova obra",
        url="https://example.test/item",
        channel="Fonte",
        category="anime",
        duration=0,
        upload_date=None,
        thumbnail=None,
        description=description,
        source=source,
    )


def test_release_date_today_or_past_blocks_publication() -> None:
    today = date(2026, 9, 29)
    for day in ("2026-09-28", "2026-09-29"):
        analysis = analysis_from_json(candidate(), {"is_release_signal": True, "release_date": day})
        assert already_released(analysis, today)
    future = analysis_from_json(candidate(), {"release_date": "2026-09-30"})
    assert not already_released(future, today)


def test_released_status_blocks_even_without_date() -> None:
    analysis = analysis_from_json(candidate(), {"release_status": "released"})
    assert already_released(analysis, date(2026, 9, 29))


def test_unknown_date_does_not_invent_a_release() -> None:
    analysis = analysis_from_json(candidate(), {"release_date": "em breve"})
    assert not already_released(analysis, date(2026, 9, 29))
    assert not confirmed_upcoming(analysis, date(2026, 9, 29))


def test_kitsu_fallback_uses_source_start_date() -> None:
    analysis = fallback_analysis(candidate("kitsu", "Estreia prevista: 2026-09-01"), "")
    assert already_released(analysis, date(2026, 9, 29))


def test_source_date_overrides_unknown_model_date() -> None:
    analysis = analysis_from_json(
        candidate("kitsu", "Estreia prevista: 2026-09-01"),
        {"is_release_signal": True, "release_date": ""},
    )
    assert already_released(analysis, date(2026, 9, 29))


def test_explicit_future_date_confirms_upcoming_without_model_status() -> None:
    analysis = analysis_from_json(candidate(), {"release_date": "2026-10-01"})
    assert confirmed_upcoming(analysis, date(2026, 9, 29))


def test_past_date_overrides_upcoming_label() -> None:
    analysis = analysis_from_json(
        candidate(), {"release_date": "2026-09-01", "release_status": "upcoming"}
    )
    assert not confirmed_upcoming(analysis, date(2026, 9, 29))
