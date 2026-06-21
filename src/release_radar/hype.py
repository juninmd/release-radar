from __future__ import annotations

from .models import ReleaseAnalysis

# Palavras no campo release_window que indicam proximidade -> mais hype.
_SOON_WORDS = (
    "hoje",
    "amanha",
    "amanhã",
    "semana",
    "breve",
    "ja disponivel",
    "já disponível",
    "disponivel",
    "disponível",
    "agora",
    "2025",
    "2026",
)


def hype_score(analysis: ReleaseAnalysis) -> int:
    """Pontua 0-100 o quao 'imperdivel' e um lancamento, de forma deterministica.

    Combina a confianca do analisador, o sinal de lancamento, a amplitude de
    plataformas/generos e a proximidade declarada da janela de lancamento.
    """
    score = round(max(0.0, min(1.0, analysis.confidence)) * 55)
    if analysis.is_release_signal:
        score += 20
    score += min(len(analysis.platforms), 3) * 5
    score += min(len(analysis.genres), 2) * 3
    window = analysis.release_window.lower()
    if any(word in window for word in _SOON_WORDS):
        score += 10
    return max(0, min(100, score))


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
