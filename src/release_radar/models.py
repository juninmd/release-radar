from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ReleaseCandidate:
    # Ids do YouTube seguem crus (compatibilidade com linhas ja gravadas);
    # as demais fontes prefixam com o proprio nome, ex.: "steam:730".
    external_id: str
    title: str
    url: str
    channel: str
    category: str
    duration: int
    upload_date: str | None
    thumbnail: str | None
    description: str = ""
    source: str = "youtube"


@dataclass(frozen=True)
class HypeSignals:
    """Notas 0-10 dadas pela LLM a partir do conhecimento previo sobre a obra."""

    fanbase: int = 0  # tamanho/engajamento da base de fas da franquia, IP ou elenco
    pedigree: int = 0  # qualidade esperada por estudio, diretor, showrunner ou dev
    track_record: int = 0  # historico de notas (IMDb, Metacritic, Steam, MAL) e bilheteria
    buzz: int = 0  # momento: anuncio inedito, evento, retorno aguardado, viralizacao
    rationale: str = ""


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
    hype: HypeSignals = field(default_factory=HypeSignals)
    raw: dict[str, Any] = field(default_factory=dict)
    release_date: str = ""
    release_status: str = "unknown"
    # trailer|teaser|announcement|clip|other|unknown: clipe/comentario nao e trailer de estreia.
    content_type: str = "unknown"

    @property
    def summary(self) -> str:
        parts = [
            self.synopsis,
            self.trailer_reading,
            self.transcript_summary,
            self.why_it_matters,
        ]
        return "\n\n".join(part for part in parts if part)
