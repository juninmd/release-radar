from __future__ import annotations

import re
from datetime import date

from .models import ReleaseAnalysis

# Palavras inteiras no release_window que indicam proximidade -> mais hype.
_SOON_WORDS = frozenset(
    {
        "hoje",
        "amanha",
        "amanhã",
        "semana",
        "breve",
        "agora",
        "disponivel",
        "disponível",
    }
)

# Pesos dos sinais 0-10 avaliados pela LLM (somam 1). Buzz pesa tanto quanto a base de
# fas porque hype e momento, nao so tamanho de franquia.
_SIGNAL_WEIGHTS = {"fanbase": 0.30, "buzz": 0.30, "track_record": 0.20, "pedigree": 0.20}
# Parte do score central que vem do melhor sinal isolado: uma IP gigante ou um anuncio
# viral esquenta mesmo que os demais sinais sejam medianos.
_PEAK_SHARE = 0.25
# Curva levemente convexa: notas medianas nao inflam, so os extremos chegam ao topo.
_CURVE = 1.2
_SIGNAL_POINTS = 70
_TIMING_POINTS = 20

# Anuncio inedito esquenta mais que mais um trailer; classificacao desconhecida vale o meio-termo.
_TYPE_POINTS = {"announcement": 10, "trailer": 7, "teaser": 6, "unknown": 4}

# (dias ate a estreia, pontos): quanto mais perto, mais acionavel.
_COUNTDOWN = ((30, 20), (90, 18), (180, 15), (365, 11), (730, 6))
_FAR_FUTURE_POINTS = 2


def hype_score(analysis: ReleaseAnalysis, today: date | None = None) -> int:
    """Pontua 0-100 o quao 'imperdivel' e um lancamento, de forma deterministica.

    Ate 70 pontos vem do conhecimento previo da LLM (base de fas, buzz, historico de
    notas, pedigree), escalados pela confianca na identificacao: nota alta para uma obra
    que a propria LLM mal identificou nao merece crédito. Ate 20 vem da proximidade da
    estreia (data exata > janela declarada) e ate 10 do tipo de conteudo. Item que nao e
    sinal de estreia nao ganha pontos de timing nem de tipo. Sem sinais da LLM o teto e 30.
    """
    today = today or date.today()
    signals = {name: max(0, min(10, getattr(analysis.hype, name))) for name in _SIGNAL_WEIGHTS}
    mean = sum(signals[name] * weight for name, weight in _SIGNAL_WEIGHTS.items())
    peak = max(signals["fanbase"], signals["buzz"])
    core = (1 - _PEAK_SHARE) * mean + _PEAK_SHARE * peak
    reliability = 0.6 + 0.4 * max(0.0, min(1.0, analysis.confidence))
    score = _SIGNAL_POINTS * (core / 10) ** _CURVE * reliability
    if analysis.is_release_signal:
        score += timing_points(analysis, today)
        score += _TYPE_POINTS.get(analysis.content_type, 0)
    return max(0, min(100, round(score)))


def timing_points(analysis: ReleaseAnalysis, today: date) -> int:
    """0-20: data exata pesa mais que a janela declarada; estreia passada nao pontua."""
    try:
        release = date.fromisoformat(analysis.release_date)
    except ValueError:
        release = None
    if release is not None:
        days = (release - today).days
        if days < 0:
            return 0
        return next((points for limit, points in _COUNTDOWN if days <= limit), _FAR_FUTURE_POINTS)
    words = _window_words(analysis.release_window)
    if words & _SOON_WORDS:
        return 17
    years = _window_years(words)
    if today.year in years:
        return 11
    if today.year + 1 in years:
        return 6
    return 0


def _window_words(window: str) -> set[str]:
    return set(re.findall(r"\w+", window.lower()))


def _window_years(words: set[str]) -> set[int]:
    return {int(word) for word in words if len(word) == 4 and word.isdigit()}


def is_soon(window: str, today: date) -> bool:
    """Janela declarada aponta para agora, este ano ou o proximo."""
    words = _window_words(window)
    if words & _SOON_WORDS:
        return True
    return any(today.year <= year <= today.year + 1 for year in _window_years(words))


def hype_badge(score: int) -> str:
    """Rotulo curto + barra visual de 10 blocos para o score."""
    if score >= 80:
        label = "🔥🔥🔥 HYPE MAXIMO"
    elif score >= 60:
        label = "🔥🔥 Alta"
    elif score >= 40:
        label = "🔥 Media"
    elif score >= 20:
        label = "🌡 Morna"
    else:
        label = "🧊 Fria"
    filled = round(score / 10)
    bar = "█" * filled + "░" * (10 - filled)
    return f"{label} {bar} {score}/100"
