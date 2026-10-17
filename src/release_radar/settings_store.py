"""Ajustes editaveis pelo painel/app desktop, guardados no banco.

As fontes e limites continuam vindo do ambiente (.env); o que for salvo aqui
sobrescreve apenas os campos da lista branca. Segredos (tokens, chaves de
analise e a conexao com o banco) nunca passam por este caminho.
"""

from __future__ import annotations

import ipaddress
from typing import Any
from urllib.parse import urlsplit

import psycopg2
from psycopg2.extras import Json, RealDictCursor

from .config import Settings

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
}

# Faixas defensivas: um ajuste absurdo gastaria LLM, disco e banda.
INT_LIMITS: dict[str, tuple[int, int]] = {
    "rss_limit": (0, 50),
    "source_limit": (0, 50),
    "max_items_per_run": (1, 200),
    "max_transcription_seconds": (0, 3600),
    "steam_limit": (0, 50),
    "kitsu_limit": (0, 50),
}

_TRUE = {"1", "true", "on", "yes", "sim"}
_FALSE = {"0", "false", "off", "no", "nao", "não", ""}
_BLOCKED_SUFFIXES = (".local", ".internal", ".localhost", ".cluster.local", ".svc")


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
        _assert_public_url(field, target)
    return text


def _assert_public_url(field: str, target: str) -> None:
    parsed = urlsplit(target)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError(f"{field}: use uma URL http(s) por entrada")
    host = (parsed.hostname or "").lower().rstrip(".")
    if not host or _is_internal_host(host):
        raise ValueError(f"{field}: host interno nao permitido ({target})")


def _is_internal_host(host: str) -> bool:
    if host in {"localhost", "metadata.google.internal"} or host.endswith(_BLOCKED_SUFFIXES):
        return True
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    return (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
        or address.is_multicast
        or address.is_unspecified
    )


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


def write_overrides(
    conn: psycopg2.extensions.connection, values: dict[str, Any]
) -> dict[str, Any]:
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
