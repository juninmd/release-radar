from __future__ import annotations

import logging
from html import escape as html_escape

from telegram import Bot

from .hype import hype_badge, hype_score
from .links import link_kind
from .models import ReleaseAnalysis, ReleaseCandidate

logger = logging.getLogger(__name__)

TELEGRAM_MAX_LEN = 4096
CAPTION_MAX_LEN = 1024


class TelegramPublisher:
    def __init__(self, bot_token: str, chat_id: str) -> None:
        self.bot_token = bot_token
        self.chat_id = chat_id
        self._bot: Bot | None = None

    @property
    def bot(self) -> Bot | None:
        if not self.bot_token or not self.chat_id:
            return None
        if self._bot is None:
            self._bot = Bot(self.bot_token)
        return self._bot

    async def publish(self, candidate: ReleaseCandidate, analysis: ReleaseAnalysis) -> bool:
        bot = self.bot
        if bot is None:
            logger.warning("Telegram not configured; skipping %s", candidate.external_id)
            return False

        text = format_message(candidate, analysis)
        caption = format_caption(candidate, analysis)
        try:
            if candidate.thumbnail:
                await bot.send_photo(
                    chat_id=self.chat_id,
                    photo=candidate.thumbnail,
                    caption=caption[:CAPTION_MAX_LEN],
                    parse_mode="HTML",
                )
                await bot.send_message(
                    chat_id=self.chat_id,
                    text=text,
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                )
            else:
                await bot.send_message(
                    chat_id=self.chat_id,
                    text=text,
                    parse_mode="HTML",
                    disable_web_page_preview=False,
                )
            return True
        except Exception:
            logger.exception("Failed to publish %s", candidate.external_id)
            return False


def format_caption(candidate: ReleaseCandidate, analysis: ReleaseAnalysis) -> str:
    return "\n".join(
        [
            f"🚨 <b>{escape(analysis.title)}</b>",
            f"🎭 {category_label(analysis.category)} | {escape(candidate.channel)}",
            *content_line(analysis),
            escape(hype_badge(hype_score(analysis))),
            f"🗓 {escape(analysis.release_window)}",
            f'{link_icon(candidate)} <a href="{escape(candidate.url)}">{link_label(candidate)}</a>',
        ]
    )


def format_message(candidate: ReleaseCandidate, analysis: ReleaseAnalysis) -> str:
    lines = [
        f"🚨 <b>{escape(analysis.title)}</b>",
        f"🎭 Categoria: {category_label(analysis.category)}",
        f"📺 Fonte: {escape(candidate.channel)}",
        *content_line(analysis),
        f"🗓 Estreia prevista: {escape(analysis.release_window)}",
        f"🎯 Confiança na identificação: {analysis.confidence:.0%}",
        escape(hype_badge(hype_score(analysis))),
    ]
    if analysis.hype.rationale:
        lines.append(f"💡 {escape(analysis.hype.rationale)}")
    if analysis.platforms:
        lines.append(f"🕹 Onde assistir ou jogar: {escape(', '.join(analysis.platforms))}")
    if analysis.genres:
        lines.append(f"🏷 Gêneros: {escape(', '.join(analysis.genres))}")
    lines.extend(
        [
            f'{link_icon(candidate)} <a href="{escape(candidate.url)}">'
            f"Abrir {link_label(candidate).lower()}</a>",
            "",
            "📝 <b>Sinopse</b>",
            escape(analysis.synopsis),
        ]
    )
    if candidate.source == "youtube":
        lines.extend(
            [
                "",
                "🎬 <b>Leitura do trailer</b>",
                escape(analysis.trailer_reading),
                "",
                "🗣 <b>Resumo transcrito</b>",
                escape(analysis.transcript_summary or "Não há falas transcritas disponíveis."),
            ]
        )
    lines.extend(
        [
            "",
            "🔥 <b>Por que acompanhar</b>",
            escape(analysis.why_it_matters),
            "",
            "👥 <b>Para quem é</b>",
            escape(analysis.audience),
        ]
    )
    if analysis.tags:
        lines.extend(["", "🔎 " + escape(" ".join(f"#{tag}" for tag in analysis.tags[:12]))])
    text = "\n".join(line for line in lines if line is not None)
    if len(text) <= TELEGRAM_MAX_LEN:
        return text
    return text[: TELEGRAM_MAX_LEN - 80].rsplit("\n", 1)[0] + "\n\n⚠️ Mensagem truncada."


CONTENT_LABELS = {"trailer": "Trailer", "teaser": "Teaser", "announcement": "Anúncio"}


def content_line(analysis: ReleaseAnalysis) -> list[str]:
    label = CONTENT_LABELS.get(analysis.content_type)
    return [f"🎞 Tipo: {label}"] if label else []


def escape(text: str) -> str:
    return html_escape(text, quote=True)


def link_label(candidate: ReleaseCandidate) -> str:
    return {"video": "Vídeo no YouTube", "article": "Artigo", "catalog": "Página oficial"}[
        link_kind(candidate.url, candidate.source)
    ]


def link_icon(candidate: ReleaseCandidate) -> str:
    return {"video": "▶️", "article": "📰", "catalog": "🔗"}[
        link_kind(candidate.url, candidate.source)
    ]


def category_label(category: str) -> str:
    return {"movies": "Filmes", "series": "Séries", "games": "Jogos", "anime": "Animes"}.get(
        category, "Outras novidades"
    )
