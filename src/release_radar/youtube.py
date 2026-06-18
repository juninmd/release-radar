from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yt_dlp

from .models import ReleaseCandidate

logger = logging.getLogger(__name__)


def get_channel_candidates(
    category: str,
    channel: str,
    limit: int,
    max_duration: int,
) -> list[ReleaseCandidate]:
    url = f"https://www.youtube.com/{channel}/videos"
    opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "flat_playlist": True,
        "extract_flat": True,
        "playlistend": limit * 3,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:  # type: ignore
            info = ydl.extract_info(url, download=False)
    except Exception:
        logger.exception("Failed to fetch channel %s", channel)
        return []

    entries = info.get("entries", []) if info else []
    candidates: list[ReleaseCandidate] = []
    for entry in entries:
        if not entry:
            continue
        duration = int(entry.get("duration") or 0)
        if duration <= 0 or duration > max_duration:
            continue
        if entry.get("live_status") == "is_upcoming":
            continue
        video_id = str(entry.get("id") or "")
        if not video_id:
            continue
        candidates.append(
            ReleaseCandidate(
                youtube_id=video_id,
                title=str(entry.get("title") or ""),
                url=f"https://www.youtube.com/watch?v={video_id}",
                channel=str(entry.get("channel") or channel.lstrip("@")),
                category=category,
                duration=duration,
                upload_date=entry.get("upload_date"),
                thumbnail=entry.get("thumbnail")
                or f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
            )
        )
    candidates.sort(key=lambda item: item.upload_date or "", reverse=True)
    return candidates[:limit]


def enrich_candidate(candidate: ReleaseCandidate) -> ReleaseCandidate:
    opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:  # type: ignore
            info = ydl.extract_info(candidate.url, download=False)
    except Exception:
        logger.exception("Failed to enrich video %s", candidate.youtube_id)
        return candidate

    description = str(info.get("description") or "")
    thumbnail = info.get("thumbnail") or candidate.thumbnail
    duration = int(info.get("duration") or candidate.duration)
    return ReleaseCandidate(
        youtube_id=candidate.youtube_id,
        title=str(info.get("title") or candidate.title),
        url=candidate.url,
        channel=str(info.get("channel") or candidate.channel),
        category=candidate.category,
        duration=duration,
        upload_date=info.get("upload_date") or candidate.upload_date,
        thumbnail=thumbnail,
        description=description,
    )


def download_audio(candidate: ReleaseCandidate, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    opts: dict[str, Any] = {
        "format": "bestaudio",
        "outtmpl": str(output_dir / "%(id)s.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "wav"}],
        "postprocessor_args": {"ffmpeg": ["-ar", "16000", "-ac", "1"]},
    }
    with yt_dlp.YoutubeDL(opts) as ydl:  # type: ignore
        info = ydl.extract_info(candidate.url, download=True)
    video_id = str(info.get("id") or candidate.youtube_id)
    wav_path = output_dir / f"{video_id}.wav"
    if not wav_path.exists():
        raise FileNotFoundError(f"Expected WAV file not found: {wav_path}")
    return wav_path
