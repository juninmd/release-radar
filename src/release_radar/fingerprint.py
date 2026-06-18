from __future__ import annotations

import hashlib
import re


def normalize_text(value: str) -> str:
    text = value.lower()
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"[^a-z0-9\u00c0-\u024f]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def content_hash(*parts: str) -> str:
    normalized = "\n".join(normalize_text(part) for part in parts if part)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
