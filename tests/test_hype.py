from datetime import date

from release_radar.hype import hype_badge, hype_score, is_soon
from release_radar.models import HypeSignals, ReleaseAnalysis

TODAY = date(2026, 9, 8)


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


FRANCHISE = HypeSignals(fanbase=9, pedigree=8, track_record=9, buzz=8, rationale="GTA")
UNKNOWN_INDIE = HypeSignals(fanbase=2, pedigree=2, track_record=1, buzz=3, rationale="novo")


def test_hype_score_high_for_beloved_franchise() -> None:
    assert hype_score(_analysis(hype=FRANCHISE), today=TODAY) >= 80


def test_fanbase_and_track_record_outweigh_release_metadata() -> None:
    # Mesmo trailer, mesma confianca: a franquia consagrada tem de vencer o
    # desconhecido, senao o score nao mede hype e sim metadados de coleta.
    franchise = hype_score(_analysis(hype=FRANCHISE), today=TODAY)
    indie = hype_score(_analysis(hype=UNKNOWN_INDIE), today=TODAY)
    assert franchise - indie >= 40


def test_hype_score_without_llm_signals_stays_lukewarm() -> None:
    # Fallback heuristico nao conhece a obra: nunca deve gritar HYPE MAXIMO.
    assert hype_score(_analysis(), today=TODAY) <= 30


def test_hype_score_low_for_cold_item() -> None:
    cold = _analysis(
        is_release_signal=False,
        platforms=[],
        genres=[],
        release_window="desconhecido",
        confidence=0.1,
    )
    assert hype_score(cold, today=TODAY) < 20


def test_hype_score_is_bounded() -> None:
    maxed = _analysis(
        confidence=5.0,
        hype=HypeSignals(fanbase=50, pedigree=50, track_record=50, buzz=50),
    )
    assert 0 <= hype_score(maxed, today=TODAY) <= 100
    negative = _analysis(hype=HypeSignals(fanbase=-5, pedigree=-5, track_record=-5, buzz=-5))
    assert hype_score(negative, today=TODAY) >= 0


def test_is_soon_matches_current_and_next_year_only() -> None:
    assert is_soon("Q4 2026", TODAY)
    assert is_soon("2027", TODAY)
    assert not is_soon("2025", TODAY)
    assert not is_soon("2028", TODAY)


def test_is_soon_matches_whole_words_only() -> None:
    assert is_soon("ja disponivel", TODAY)
    assert is_soon("Já disponível", TODAY)
    assert not is_soon("indisponivel no Brasil", TODAY)
    assert not is_soon("desconhecido", TODAY)


def test_hype_badge_has_bar_and_value() -> None:
    badge = hype_badge(75)
    assert "75/100" in badge
    assert "█" in badge and "░" in badge
