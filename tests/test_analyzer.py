from release_radar.analyzer import analysis_from_json, fallback_analysis
from release_radar.models import ReleaseCandidate


def make_candidate(title: str = "Big Game - Launch Trailer") -> ReleaseCandidate:
    return ReleaseCandidate(
        external_id="abc",
        title=title,
        url="https://youtu.be/abc",
        channel="Canal",
        category="games",
        duration=90,
        upload_date=None,
        thumbnail=None,
    )


def test_analysis_from_json_defaults_to_candidate_values() -> None:
    analysis = analysis_from_json(make_candidate(), {"is_release_signal": True})
    assert analysis.title == "Big Game - Launch Trailer"
    assert analysis.category == "games"
    assert analysis.is_release_signal is True


def test_non_boolean_signal_does_not_authorize_publication() -> None:
    analysis = analysis_from_json(
        make_candidate(), {"is_release_signal": "false", "release_status": "upcoming"}
    )
    assert not analysis.is_release_signal


def test_fallback_identifies_release_words() -> None:
    analysis = fallback_analysis(make_candidate(), "")
    assert analysis.is_release_signal is True


def test_fallback_treats_upcoming_store_sources_as_release_signal() -> None:
    candidate = ReleaseCandidate(
        external_id="steam:1",
        title="Halloween: The Game",
        url="https://store.steampowered.com/app/1/",
        channel="Steam",
        category="games",
        duration=0,
        upload_date="20260908",
        thumbnail=None,
        source="steam",
    )

    # Sem LLM, o titulo de loja nao casa com palavra-chave; a fonte e o sinal.
    assert fallback_analysis(candidate, transcript="").is_release_signal


def test_fallback_still_rejects_unrelated_youtube_title() -> None:
    candidate = make_candidate(title="Bastidores do estudio")
    assert not fallback_analysis(candidate, transcript="").is_release_signal


def test_analysis_from_json_parses_and_clamps_hype_signals() -> None:
    analysis = analysis_from_json(
        make_candidate(),
        {
            "is_release_signal": True,
            "hype": {
                "fanbase": 9,
                "pedigree": "7",
                "track_record": 42,
                "buzz": -3,
                "rationale": "Franquia consagrada",
            },
        },
    )
    assert analysis.hype.fanbase == 9
    assert analysis.hype.pedigree == 7
    assert analysis.hype.track_record == 10
    assert analysis.hype.buzz == 0
    assert analysis.hype.rationale == "Franquia consagrada"


def test_analysis_from_json_tolerates_missing_or_malformed_hype() -> None:
    assert analysis_from_json(make_candidate(), {}).hype.fanbase == 0
    assert analysis_from_json(make_candidate(), {"hype": "n/a"}).hype.fanbase == 0
    assert analysis_from_json(make_candidate(), {"hype": {"fanbase": "alto"}}).hype.fanbase == 0


def test_title_that_is_a_clip_overrides_what_the_llm_claims() -> None:
    clip = ReleaseCandidate(
        external_id="clip",
        title="Dune: Part Three | Movie Clip",
        url="https://youtu.be/clip",
        channel="Canal",
        category="movies",
        duration=60,
        upload_date=None,
        thumbnail=None,
    )

    analysis = analysis_from_json(clip, {"is_release_signal": True, "content_type": "trailer"})

    assert analysis.content_type == "clip"


def test_unknown_content_type_from_llm_is_normalised() -> None:
    video = ReleaseCandidate(
        external_id="v",
        title="Dune: Part Three",
        url="https://youtu.be/v",
        channel="Canal",
        category="movies",
        duration=60,
        upload_date=None,
        thumbnail=None,
    )

    assert analysis_from_json(video, {"content_type": " Teaser "}).content_type == "teaser"
    assert analysis_from_json(video, {"content_type": "banana"}).content_type == "unknown"
