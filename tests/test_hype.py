from release_radar.hype import hype_badge, hype_score
from release_radar.models import ReleaseAnalysis


def _analysis(**overrides) -> ReleaseAnalysis:
    base = dict(
        is_release_signal=True,
        category="games",
        title="Jogo X",
        original_title="Game X",
        release_window="2026",
        platforms=["PC", "PS5"],
        genres=["RPG"],
        synopsis="s",
        trailer_reading="t",
        transcript_summary="r",
        why_it_matters="w",
        audience="a",
        confidence=0.9,
        tags=[],
    )
    base.update(overrides)
    return ReleaseAnalysis(**base)


def test_hype_score_high_for_strong_signal() -> None:
    assert hype_score(_analysis()) >= 80


def test_hype_score_low_for_cold_item() -> None:
    cold = _analysis(
        is_release_signal=False,
        platforms=[],
        genres=[],
        release_window="desconhecido",
        confidence=0.1,
    )
    assert hype_score(cold) < 20


def test_hype_score_is_bounded() -> None:
    maxed = _analysis(
        confidence=5.0,
        platforms=["a", "b", "c", "d", "e"],
        genres=["a", "b", "c", "d"],
    )
    assert 0 <= hype_score(maxed) <= 100


def test_hype_badge_has_bar_and_value() -> None:
    badge = hype_badge(75)
    assert "75/100" in badge
    assert "█" in badge and "░" in badge
