from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ReleaseCandidate:
    youtube_id: str
    title: str
    url: str
    channel: str
    category: str
    duration: int
    upload_date: str | None
    thumbnail: str | None
    description: str = ""


@dataclass(frozen=True)
class ReleaseAnalysis:
    is_release_signal: bool
    category: str
    title: str
    original_title: str
    release_window: str
    platforms: list[str]
    genres: list[str]
    synopsis: str
    trailer_reading: str
    transcript_summary: str
    why_it_matters: str
    audience: str
    confidence: float
    tags: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def summary(self) -> str:
        parts = [
            self.synopsis,
            self.trailer_reading,
            self.transcript_summary,
            self.why_it_matters,
        ]
        return "\n\n".join(part for part in parts if part)
