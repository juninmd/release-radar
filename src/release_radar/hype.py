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

# Pesos dos sinais 0-10 avaliados pela LLM; somam 70 dos 100 pontos.
_SIGNAL_WEIGHTS = {"fanbase": 2.5, "track_record": 2.0, "pedigree": 1.5, "buzz": 1.0}


def hype_score(analysis: ReleaseAnalysis, today: date | None = None) -> int:
    """Pontua 0-100 o quao 'imperdivel' e um lancamento, de forma deterministica.

    70 pontos vem do conhecimento previo da LLM (base de fas, historico de
    notas, pedigree, buzz); 30 vem de metadados do proprio item (confianca,
    sinal de lancamento, proximidade). Sem sinais da LLM o teto e 30.
    """
    score = sum(
        max(0, min(10, getattr(analysis.hype, name))) * weight
        for name, weight in _SIGNAL_WEIGHTS.items()
    )
    score += max(0.0, min(1.0, analysis.confidence)) * 10
    if analysis.is_release_signal:
        score += 10
    if is_soon(analysis.release_window, today or date.today()):
        score += 10
    return max(0, min(100, round(score)))


def is_soon(window: str, today: date) -> bool:
    """Janela declarada aponta para agora, este ano ou o proximo."""
    words = set(re.findall(r"\w+", window.lower()))
    if words & _SOON_WORDS:
        return True
    years = {int(word) for word in words if len(word) == 4 and word.isdigit()}
    return any(today.year <= year <= today.year + 1 for year in years)


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
