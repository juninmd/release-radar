from __future__ import annotations

import json
import logging
from typing import Any

from openai import OpenAI

from .models import HypeSignals, ReleaseAnalysis, ReleaseCandidate

logger = logging.getLogger(__name__)


def analyze_release(
    candidate: ReleaseCandidate,
    transcript: str,
    base_url: str,
    api_key: str,
    model: str,
    timeout: float,
) -> ReleaseAnalysis:
    if not api_key:
        return fallback_analysis(candidate, transcript)

    client = OpenAI(base_url=base_url, api_key=api_key, timeout=timeout)
    response = client.chat.completions.create(
        model=model,
        temperature=0.2,
        messages=[
            {
                "role": "system",
                "content": (
                    "Voce e um editor senior de cultura pop. Analise trailers/anuncios de "
                    "filmes, series, jogos e animes. Responda apenas JSON valido, sem markdown."
                ),
            },
            {
                "role": "user",
                "content": build_prompt(candidate, transcript),
            },
        ],
    )
    raw_text = response.choices[0].message.content or "{}"
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError:
        logger.warning("LLM returned invalid JSON for %s", candidate.external_id)
        return fallback_analysis(candidate, transcript, raw_text)
    return analysis_from_json(candidate, data)


def build_prompt(candidate: ReleaseCandidate, transcript: str) -> str:
    return f"""
Analise se isto e lancamento/anuncio/trailer relevante. Se for noticia fria,
rumor sem material novo, clip antigo ou compilado, marque is_release_signal=false.

Categoria esperada: {candidate.category}
Fonte: {candidate.source} ({candidate.channel})
Titulo: {candidate.title}
URL: {candidate.url}
Descricao/metadados da fonte:
{candidate.description[:8000]}

Transcricao do trailer/video (vazio quando a fonte nao tem video):
{transcript[:12000]}

Avalie tambem o potencial de hype com notas inteiras de 0 a 10, usando seu
conhecimento previo sobre a obra, a franquia e os criadores:
- fanbase: tamanho e engajamento da base de fas da franquia, IP ou elenco
  (0 = IP inedito sem publico formado, 10 = fenomeno global).
- pedigree: qualidade esperada pelo estudio, diretor, showrunner,
  desenvolvedora ou autor envolvidos.
- track_record: historico de recepcao das obras anteriores da franquia e dos
  criadores (IMDb, Rotten Tomatoes, Metacritic, reviews da Steam,
  MyAnimeList) e desempenho comercial.
- buzz: momento do anuncio: inedito, evento grande, retorno muito aguardado,
  viralizacao.
Se nao reconhecer a obra nem os criadores, de notas baixas (0-3) e diga isso
na rationale. Nunca invente notas, premios ou bilheterias.

Retorne JSON com este schema:
{{
  "is_release_signal": true,
  "category": "movies|series|games|anime|unknown",
  "title": "nome comercial em PT-BR quando possivel",
  "original_title": "titulo original",
  "release_window": "data, janela ou desconhecido",
  "platforms": ["cinema", "Netflix", "PS5"],
  "genres": ["acao"],
  "synopsis": "sinopse rica em 2-4 frases",
  "trailer_reading": "analise visual/narrativa do trailer: tom, conflito, imagens, promessa",
  "transcript_summary": "resumo do conteudo falado/narrado, com pontos concretos",
  "why_it_matters": "por que vale acompanhar, contexto de franquia/estudio/publico",
  "audience": "para quem e indicado",
  "tags": ["trailer", "estreia"],
  "confidence": 0.0,
  "hype": {{
    "fanbase": 0,
    "pedigree": 0,
    "track_record": 0,
    "buzz": 0,
    "rationale": "1-2 frases citando franquia, criadores e notas historicas"
  }}
}}
""".strip()


def analysis_from_json(candidate: ReleaseCandidate, data: dict[str, Any]) -> ReleaseAnalysis:
    return ReleaseAnalysis(
        is_release_signal=bool(data.get("is_release_signal")),
        category=str(data.get("category") or candidate.category),
        title=str(data.get("title") or candidate.title),
        original_title=str(data.get("original_title") or candidate.title),
        release_window=str(data.get("release_window") or "desconhecido"),
        platforms=[str(item) for item in data.get("platforms", []) if item],
        genres=[str(item) for item in data.get("genres", []) if item],
        synopsis=str(data.get("synopsis") or ""),
        trailer_reading=str(data.get("trailer_reading") or ""),
        transcript_summary=str(data.get("transcript_summary") or ""),
        why_it_matters=str(data.get("why_it_matters") or ""),
        audience=str(data.get("audience") or ""),
        confidence=float(data.get("confidence") or 0.0),
        tags=[str(item) for item in data.get("tags", []) if item],
        hype=hype_from_json(data.get("hype")),
        raw=data,
    )


def hype_from_json(data: Any) -> HypeSignals:
    if not isinstance(data, dict):
        return HypeSignals()
    return HypeSignals(
        fanbase=_signal(data.get("fanbase")),
        pedigree=_signal(data.get("pedigree")),
        track_record=_signal(data.get("track_record")),
        buzz=_signal(data.get("buzz")),
        rationale=str(data.get("rationale") or ""),
    )


def _signal(value: Any) -> int:
    try:
        return max(0, min(10, int(float(value))))
    except (TypeError, ValueError):
        return 0


def fallback_analysis(
    candidate: ReleaseCandidate,
    transcript: str,
    raw_text: str = "",
) -> ReleaseAnalysis:
    title_l = candidate.title.lower()
    release_words = (
        "trailer",
        "teaser",
        "launch",
        "release",
        "estreia",
        "lancamento",
        "lançamento",
        "gameplay",
        "announcement",
    )
    # Steam e Kitsu ja entregam so itens nao lancados; sem LLM, o titulo sozinho
    # ("Halloween: The Game") nunca casaria com as palavras-chave.
    is_release = candidate.source in ("steam", "kitsu") or any(
        word in title_l for word in release_words
    )
    summary = candidate.description[:700] or transcript[:700]
    return ReleaseAnalysis(
        is_release_signal=is_release,
        category=candidate.category,
        title=candidate.title,
        original_title=candidate.title,
        release_window="desconhecido",
        platforms=[],
        genres=[],
        synopsis=summary,
        trailer_reading=(
            "Analise LLM indisponivel; item identificado por heuristica do titulo/descricao."
        ),
        transcript_summary=transcript[:700],
        why_it_matters="Requer revisao posterior com LLM para contexto completo.",
        audience="Publico interessado em novidades de cultura pop.",
        confidence=0.35 if is_release else 0.1,
        tags=["heuristic"],
        raw={"fallback": True, "raw_text": raw_text},
    )
