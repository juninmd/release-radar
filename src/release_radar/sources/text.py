from __future__ import annotations

import html
import re

_TAG_RE = re.compile(r"<[^>]+>")
_BREAK_RE = re.compile(r"<\s*br\s*/?\s*>", re.IGNORECASE)
_SPACES_RE = re.compile(r"[ \t]+")


def strip_html(value: object, limit: int = 1200) -> str:
    """Sinopses de APIs vem com <p>/<br>/<i>; o prompt da LLM quer texto puro."""
    text = _BREAK_RE.sub("\n", str(value or ""))
    text = html.unescape(_TAG_RE.sub("", text))
    text = _SPACES_RE.sub(" ", text).strip()
    return text[:limit]
