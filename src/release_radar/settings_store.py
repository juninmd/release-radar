"""Ajustes editaveis pelo painel/app desktop, guardados no banco.

As fontes e limites continuam vindo do ambiente (.env); o que for salvo aqui
sobrescreve apenas os campos da lista branca. Segredos (tokens, chaves de
analise e a conexao com o banco) nunca passam por este caminho.
"""

from __future__ import annotations

from typing import Any

import psycopg2
from psycopg2.extras import Json, RealDictCursor

from .config import Settings
from .net_guard import InternalTargetError, assert_public_url

# kind: "int", "bool", "str" ou "feeds" (lista de URLs publicas). Somente estes
# campos a API expoe.
EDITABLE_FIELDS: dict[str, str] = {
    "youtube_sources": "str",
    "rss_sources": "feeds",
    "rss_limit": "int",
    "source_limit": "int",
    "max_items_per_run": "int",
    "max_transcription_seconds": "int",
    "analyze_video_content": "bool",
    "steam_enabled": "bool",
    "steam_limit": "int",
    "steam_country": "str",
    "steam_language": "str",
    "kitsu_enabled": "bool",
    "kitsu_limit": "int",
    "anilist_enabled": "bool",
    "anilist_limit": "int",
    "jikan_enabled": "bool",
    "jikan_limit": "int",
    "tvmaze_enabled": "bool",
    "tvmaze_limit": "int",
    "tvmaze_days": "int",
    "wikidata_enabled": "bool",
    "wikidata_limit": "int",
    "wikidata_days": "int",
}

# Faixas defensivas: um ajuste absurdo gastaria LLM, disco e banda.
INT_LIMITS: dict[str, tuple[int, int]] = {
    "rss_limit": (0, 50),
    "source_limit": (0, 50),
    "max_items_per_run": (1, 200),
    "max_transcription_seconds": (0, 3600),
    "steam_limit": (0, 50),
    "kitsu_limit": (0, 50),
    "anilist_limit": (0, 50),
    "jikan_limit": (0, 25),
    "tvmaze_limit": (0, 50),
    "tvmaze_days": (1, 30),
    "wikidata_limit": (0, 20),
    "wikidata_days": (1, 730),
}

_TRUE = {"1", "true", "on", "yes", "sim"}
_FALSE = {"0", "false", "off", "no", "nao", "não", ""}


def coerce(field: str, value: Any) -> Any:
    kind = EDITABLE_FIELDS[field]
    if kind == "bool":
        if isinstance(value, bool):
            return value
        if not isinstance(value, str):
            raise ValueError(f"{field} deve ser verdadeiro ou falso")
        text = value.strip().lower()
        if text in _TRUE:
            return True
        if text in _FALSE:
            return False
        raise ValueError(f"{field} deve ser verdadeiro ou falso")
    if kind == "int":
        parsed = _coerce_int(field, value)
        low, high = INT_LIMITS[field]
        if not low <= parsed <= high:
            raise ValueError(f"{field} deve estar entre {low} e {high}")
        return parsed
    if kind == "feeds":
        return _coerce_feeds(field, value)
    return str(value).strip()


def _coerce_int(field: str, value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field} deve ser um numero inteiro")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError as exc:
            raise ValueError(f"{field} deve ser um numero inteiro") from exc
    raise ValueError(f"{field} deve ser um numero inteiro")


def _coerce_feeds(field: str, value: Any) -> str:
    """Aceita apenas http(s) para hosts publicos, evitando SSRF pela API."""
    text = str(value).strip()
    for raw in text.split(","):
        entry = raw.strip()
        if not entry:
            continue
        target = entry.split("|", 1)[1].strip() if "|" in entry else entry
        try:
            assert_public_url(target)
        except InternalTargetError as error:
            raise ValueError(f"{field}: {error} ({target})") from error
    return text


def validate(values: dict[str, Any]) -> dict[str, Any]:
    unknown = set(values) - set(EDITABLE_FIELDS)
    if unknown:
        raise ValueError("campos desconhecidos: " + ", ".join(sorted(unknown)))
    return {field: coerce(field, value) for field, value in values.items()}


def read_overrides(conn: psycopg2.extensions.connection) -> dict[str, Any]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT key, value FROM radar_settings")
        rows = cur.fetchall()
    return {row["key"]: row["value"] for row in rows if row["key"] in EDITABLE_FIELDS}


def write_overrides(conn: psycopg2.extensions.connection, values: dict[str, Any]) -> dict[str, Any]:
    validated = validate(values)
    with conn.cursor() as cur:
        for field, value in validated.items():
            cur.execute(
                """
                INSERT INTO radar_settings (key, value, updated_at)
                VALUES (%s, %s, NOW())
                ON CONFLICT (key) DO UPDATE
                    SET value = EXCLUDED.value, updated_at = NOW()
                """,
                (field, Json(value)),
            )
    conn.commit()
    return validated


def effective_settings(settings: Settings, overrides: dict[str, Any]) -> Settings:
    known = {
        field: value
        for field, value in overrides.items()
        if field in EDITABLE_FIELDS and hasattr(settings, field)
    }
    return settings.model_copy(update=known) if known else settings


def public_settings(settings: Settings, overrides: dict[str, Any]) -> dict[str, Any]:
    """Valores efetivos da lista branca, sem segredos, mais a lista de sobrescritos."""
    effective = effective_settings(settings, overrides)
    return {
        "values": {field: getattr(effective, field) for field in EDITABLE_FIELDS},
        "defaults": {field: getattr(settings, field) for field in EDITABLE_FIELDS},
        "overridden": sorted(field for field in EDITABLE_FIELDS if field in overrides),
    }
