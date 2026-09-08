from __future__ import annotations

from release_radar.models import ReleaseCandidate
from release_radar.pipeline import interleave_by_source


def candidate(source: str, index: int, upload_date: str) -> ReleaseCandidate:
    return ReleaseCandidate(
        external_id=f"{source}-{index}",
        title=f"{source} {index}",
        url=f"https://example.test/{source}/{index}",
        channel=source,
        category="games",
        duration=0,
        upload_date=upload_date,
        thumbnail=None,
        source=source,
    )


def test_youtube_is_not_starved_by_fresher_feed_items() -> None:
    # Feeds/lojas chegam com a data de hoje; YouTube, com datas mais antigas.
    feed = [candidate("rss", index, "20260907") for index in range(5)]
    youtube = [candidate("youtube", index, "20260901") for index in range(5)]

    ordered = interleave_by_source(feed + youtube)

    assert [item.source for item in ordered[:4]] == ["youtube", "rss", "youtube", "rss"]
    assert len(ordered) == 10


def test_recency_is_preserved_inside_each_source() -> None:
    ordered = interleave_by_source(
        [
            candidate("rss", 1, "20260901"),
            candidate("rss", 2, "20260907"),
            candidate("rss", 3, "20260904"),
        ]
    )

    assert [item.external_id for item in ordered] == ["rss-2", "rss-3", "rss-1"]


def test_uneven_sources_keep_all_candidates() -> None:
    steam = [candidate("steam", index, "20260907") for index in range(3)]
    ordered = interleave_by_source([candidate("youtube", 0, "20260901"), *steam])

    assert len(ordered) == 4
    assert ordered[0].source == "youtube"
    assert [item.source for item in ordered[1:]] == ["steam", "steam", "steam"]


def test_empty_input_returns_empty() -> None:
    assert interleave_by_source([]) == []


def test_non_youtube_candidate_is_never_downloaded_for_transcription(monkeypatch) -> None:
    from release_radar.config import Settings
    from release_radar.pipeline import maybe_transcribe

    def fail(*args: object, **kwargs: object) -> None:
        raise AssertionError("download_audio nao deve ser chamado fora do YouTube")

    monkeypatch.setattr("release_radar.pipeline.download_audio", fail)
    steam = candidate("steam", 1, "20260907")
    settings = Settings(_env_file=None, analyze_video_content=True)

    assert maybe_transcribe(settings, steam) == ""


def test_youtube_candidate_still_transcribes(monkeypatch) -> None:
    from release_radar.config import Settings
    from release_radar.pipeline import maybe_transcribe

    monkeypatch.setattr("release_radar.pipeline.download_audio", lambda *a, **k: "audio.wav")
    monkeypatch.setattr("release_radar.pipeline.transcribe_audio", lambda *a, **k: "falado")
    settings = Settings(_env_file=None, analyze_video_content=True)

    assert maybe_transcribe(settings, candidate("youtube", 1, "20260907")) == "falado"
