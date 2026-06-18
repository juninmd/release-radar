from release_radar.models import ReleaseAnalysis, ReleaseCandidate
from release_radar.telegram_bot import format_message


def test_format_message_contains_analysis_blocks() -> None:
    candidate = ReleaseCandidate(
        youtube_id="abc",
        title="Trailer X",
        url="https://youtu.be/abc",
        channel="Canal",
        category="games",
        duration=90,
        upload_date=None,
        thumbnail=None,
    )
    analysis = ReleaseAnalysis(
        is_release_signal=True,
        category="games",
        title="Jogo X",
        original_title="Game X",
        release_window="2026",
        platforms=["PC"],
        genres=["RPG"],
        synopsis="Sinopse",
        trailer_reading="Leitura",
        transcript_summary="Resumo",
        why_it_matters="Importa",
        audience="Fans",
        confidence=0.9,
        tags=["rpg"],
    )

    text = format_message(candidate, analysis)

    assert "Sinopse" in text
    assert "Leitura do trailer" in text
    assert "Resumo transcrito" in text
    assert "PC" in text
