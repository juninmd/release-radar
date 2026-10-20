from __future__ import annotations

import logging
import re
from pathlib import Path

import psycopg2

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).with_name("sql")
_NAME_RE = re.compile(r"^(\d{4})_[a-z0-9_]+\.sql$")
# Serializa bot e painel iniciando ao mesmo tempo contra o mesmo banco.
_LOCK_KEY = 0x52454C52  # "RELR"


def discover_migrations(directory: Path = MIGRATIONS_DIR) -> list[tuple[str, Path]]:
    """Arquivos `NNNN_nome.sql` em ordem numerica; nome fora do padrao e erro."""
    found: list[tuple[str, Path]] = []
    for path in sorted(directory.glob("*.sql")):
        match = _NAME_RE.match(path.name)
        if not match:
            raise ValueError(f"Migracao com nome invalido: {path.name} (use NNNN_nome.sql)")
        found.append((match.group(1), path))
    versions = [version for version, _ in found]
    if len(set(versions)) != len(versions):
        raise ValueError("Duas migracoes com a mesma versao")
    return found


def apply_migrations(
    conn: psycopg2.extensions.connection, directory: Path = MIGRATIONS_DIR
) -> list[str]:
    """Aplica as migracoes pendentes, cada uma na sua transacao. Devolve as versoes aplicadas."""
    applied: list[str] = []
    with conn.cursor() as cur:
        cur.execute("SELECT pg_advisory_lock(%s)", (_LOCK_KEY,))
    try:
        with conn.cursor() as cur:
            cur.execute(
                """CREATE TABLE IF NOT EXISTS schema_migrations (
                       version TEXT PRIMARY KEY,
                       name TEXT NOT NULL,
                       applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                   )"""
            )
            cur.execute("SELECT version FROM schema_migrations")
            done = {row[0] for row in cur.fetchall()}
        conn.commit()
        for version, path in discover_migrations(directory):
            if version in done:
                continue
            try:
                with conn.cursor() as cur:
                    cur.execute(path.read_text(encoding="utf-8"))
                    cur.execute(
                        "INSERT INTO schema_migrations (version, name) VALUES (%s, %s)",
                        (version, path.stem),
                    )
                conn.commit()
            except Exception:
                conn.rollback()
                logger.error("Migration %s failed; rolled back", path.name)
                raise
            logger.info("Applied migration %s", path.name)
            applied.append(version)
    finally:
        conn.rollback()
        with conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_unlock(%s)", (_LOCK_KEY,))
        conn.commit()
    return applied
