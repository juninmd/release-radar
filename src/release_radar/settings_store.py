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

# kind: "int" (>= 0), "bool" ou "str". Somente estes campos a API expoe.
EDITABLE_FIELDS: dict[str, str] = {
    "youtube_sources": "str",
    "rss_sources": "str",
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

_TRUE = {"1", "true", "on", "yes", "sim"}
_FALSE = {"0", "false", "off", "no", "nao", "não", ""}


def coerce(field: str, value: Any) -> Any:
    kind = EDITABLE_FIELDS[field]
    if kind == "bool":
        if isinstance(value, bool):
            return value
        text = str(value).strip().lower()
        if text in _TRUE:
            return True
        if text in _FALSE:
            return False
        raise ValueError(f"{field} deve ser verdadeiro ou falso")
    if kind == "int":
        try:
            parsed = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{field} deve ser um numero inteiro") from exc
        if parsed < 0:
            raise ValueError(f"{field} nao pode ser negativo")
        return parsed
    return str(value).strip()


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
