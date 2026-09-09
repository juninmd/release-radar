from release_radar.db import analysis_to_json
from release_radar.models import HypeSignals, ReleaseAnalysis


def test_analysis_to_json_keeps_hype_as_nested_object_without_raw() -> None:
    # LLM que responde "{}" deixa raw vazio; o fallback tem de serializar
    # HypeSignals como objeto JSON, nao como repr em string.
    analysis = ReleaseAnalysis(
        is_release_signal=True,
        category="games",
        title="Jogo",
        original_title="Game",
        release_window="2026",
        platforms=[],
        genres=[],
        synopsis="",
        trailer_reading="",
        transcript_summary="",
        why_it_matters="",
        audience="",
        confidence=0.5,
        hype=HypeSignals(fanbase=7, rationale="franquia"),
        raw={},
    )
    payload = analysis_to_json(analysis)
    assert payload["hype"] == {
        "fanbase": 7,
        "pedigree": 0,
        "track_record": 0,
        "buzz": 0,
        "rationale": "franquia",
    }
