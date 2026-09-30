from release_radar.models import HypeSignals, ReleaseAnalysis, ReleaseCandidate
from release_radar.telegram_bot import format_message


def test_format_message_contains_analysis_blocks() -> None:
    candidate = ReleaseCandidate(
        external_id="abc",
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
        hype=HypeSignals(fanbase=8, rationale="Franquia com base fiel"),
    )

    text = format_message(candidate, analysis)

    assert "Sinopse" in text
    assert "Leitura do trailer" in text
    assert "Resumo transcrito" in text
    assert "PC" in text
    assert "Franquia com base fiel" in text


def test_article_message_has_article_link_without_video_sections() -> None:
    candidate = ReleaseCandidate(
        external_id="rss:1",
        title="Noticia",
        url="https://example.test/post?a=&quot;",
        channel="Revista",
        category="movies",
        duration=0,
        upload_date=None,
        thumbnail=None,
        source="rss",
    )
    analysis = ReleaseAnalysis(
        is_release_signal=True,
        category="movies",
        title="Filme",
        original_title="Filme",
        release_window="2027",
        platforms=[],
        genres=[],
        synopsis="Sinopse",
        trailer_reading="",
        transcript_summary="",
        why_it_matters="Importa",
        audience="Publico",
        confidence=0.8,
    )
    text = format_message(candidate, analysis)
    assert "Abrir artigo" in text
    assert "Leitura do trailer" not in text
    assert "Resumo transcrito" not in text
