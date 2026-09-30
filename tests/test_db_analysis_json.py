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


def test_analysis_serialization_keeps_canonical_values_with_raw_payload() -> None:
    from release_radar.analyzer import analysis_from_json
    from release_radar.models import ReleaseCandidate

    candidate = ReleaseCandidate(
        external_id="kitsu:1",
        title="Anime",
        url="https://kitsu.io/anime/test",
        channel="Kitsu",
        category="anime",
        duration=0,
        upload_date=None,
        thumbnail=None,
        source="kitsu",
        description="Estreia prevista: 2026-12-01",
    )
    analysis = analysis_from_json(candidate, {"release_date": "", "hype": {"fanbase": 99}})
    payload = analysis_to_json(analysis)
    assert payload["release_date"] == "2026-12-01"
    assert payload["hype"]["fanbase"] == 10
    assert payload["title"] == "Anime"
