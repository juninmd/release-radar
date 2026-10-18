from __future__ import annotations

import re
import unicodedata

# Trailer/teaser com seus modificadores ("Official Trailer #2", "Novo Trailer Oficial").
# Modificadores so saem quando colados a trailer/teaser: "Final Fantasy" e "New Super
# Mario" continuam intactos.
_LEAD = (
    r"official|oficial|final|new|novo|nova|first|primeiro|second|segundo|launch|reveal|"
    r"gameplay|cinematic|extended|international|announcement|anuncio|story|release date|"
    r"date|dublado|legendado|subtitled|dubbed|full|completo|live action|animated|tv|"
    r"world premiere|movie|film|game|series|show|anime"
)
_TAIL = r"official|oficial|dublado|legendado|subtitled|dubbed|final|completo|\d+"
_CORE = r"trailers?|teasers?|tv spot"
_TRAILER_PHRASE = re.compile(
    rf"\b(?:(?:{_LEAD}|{_CORE})\s+)*(?:{_CORE})(?:\s+(?:{_TAIL}|{_CORE}))*\b"
)
_PROMO_PHRASE = re.compile(
    r"\b(?:only |now )?(?:in theat(?:er|re)s|streaming now|nos cinemas|em breve nos cinemas|"
    r"coming soon|now streaming)\b"
)
_SEGMENT_SPLIT = re.compile(r"\s[|\-–—]\s|\s*\|\s*")
_NON_ALNUM = re.compile(r"[\W_]+")
_NOISE_TOKENS = frozenset({"hd", "4k", "uhd", "official", "oficial"})
# Segmentos so de marca/canal ("| Netflix", "| Marvel Studios") nao identificam a obra.
_BRAND_TOKENS = frozenset(
    {
        "netflix", "disney", "prime", "video", "max", "hbo", "hulu", "apple", "tv", "paramount",
        "playstation", "xbox", "nintendo", "ign", "gamespot", "youtube", "studios", "pictures",
        "entertainment", "plus", "trailers", "games", "movies",
    }
)  # fmt: skip

# Reacao/explicacao e sempre comentario; os demais termos tambem sao palavras de titulo
# ("Interview with the Vampire", "Scenes from a Marriage"), entao so valem sozinhos
# ou colados a trailer/teaser.
_COMMENTARY = (
    r"reactions?|reacts?|reacao|explained|explicado|analysis|analise|recap|compilation|"
    r"walkthrough|podcast"
)
_AMBIGUOUS = (
    r"reviews?|resenha|interviews?|entrevistas?|ranking|breakdown|top \d+|clips?|scenes?|"
    r"cenas?|sneak peek|featurette|behind the scenes|bts|making of|trecho|bastidores|shorts"
)
_ALWAYS_CLIP = re.compile(rf"\b(?:{_COMMENTARY})\b")
_ANY_AMBIGUOUS = re.compile(rf"\b(?:{_AMBIGUOUS})\b")
_HAS_TRAILER = re.compile(r"\b(?:trailers?|teasers?|tv spot)\b")
_ATTACHED_TO_TRAILER = re.compile(
    rf"\b(?:{_AMBIGUOUS})\s+(?:(?:the|official|final|new|\d+)\s+)?(?:trailers?|teasers?)\b|"
    rf"\b(?:trailers?|teasers?)\s+(?:\d+\s+)?(?:{_AMBIGUOUS})\b"
)
_TRAILER_ANY = re.compile(
    r"\b(?:trailers?|teasers?|tv spot|announcement|reveal|anuncio|first look)\b"
)


def _fold(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).lower()


def _tokens(value: str) -> list[str]:
    return _NON_ALNUM.sub(" ", value).split()


def classify_video_title(title: str) -> str:
    """Separa trailer ('trailer'), clipe/comentario ('clip') e o que so a analise decide."""
    folded = _fold(title)
    # " / " entre segmentos impede que "Breakdown | Official Trailer" pareca colado.
    text = " / ".join(" ".join(_tokens(seg)) for seg in _SEGMENT_SPLIT.split(folded))
    if _ALWAYS_CLIP.search(text):
        return "clip"
    if _HAS_TRAILER.search(text):
        return "clip" if _ATTACHED_TO_TRAILER.search(text) else "trailer"
    if _ANY_AMBIGUOUS.search(text):
        return "clip"
    return "trailer" if _TRAILER_ANY.search(text) else "unknown"


def work_key(title: str, category: str, channel: str = "") -> str:
    """Identifica a obra por tras de varios trailers/teasers do mesmo titulo."""
    folded = _fold(title)
    channel_tokens = set(_tokens(_fold(channel)))
    segments: list[list[str]] = []
    for segment in _SEGMENT_SPLIT.split(folded):
        text = _PROMO_PHRASE.sub(" ", " ".join(_tokens(segment)))
        text = _TRAILER_PHRASE.sub(" ", text)
        tokens = [token for token in text.split() if token not in _NOISE_TOKENS]
        if tokens:
            segments.append(tokens)
    allowed = _BRAND_TOKENS | channel_tokens
    work = [seg for seg in segments if not set(seg) <= allowed] or segments
    tokens = [token for seg in work for token in seg]
    # Sem obra identificavel nao ha identidade: chave vazia nunca casa com nada.
    return f"{category}:{' '.join(tokens)}" if tokens else ""
