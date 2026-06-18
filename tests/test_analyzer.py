from release_radar.analyzer import analysis_from_json, fallback_analysis
from release_radar.models import ReleaseCandidate


def make_candidate(title: str = "Big Game - Launch Trailer") -> ReleaseCandidate:
    return ReleaseCandidate(
        youtube_id="abc",
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


def test_fallback_identifies_release_words() -> None:
    analysis = fallback_analysis(make_candidate(), "")
    assert analysis.is_release_signal is True
