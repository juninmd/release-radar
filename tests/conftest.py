from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from pathlib import Path

import psycopg2
import pytest
from psycopg2 import sql
from psycopg2.extensions import make_dsn


@pytest.fixture
def postgres_dsn(tmp_path: Path) -> Iterator[str]:
    """Cada teste usa um schema isolado, nunca as tabelas do banco configurado."""
    dsn = os.environ.get("RELEASE_RADAR_TEST_DSN")
    if not dsn:
        pgserver = pytest.importorskip("pgserver", reason="requer Postgres de teste ou pgserver")
        server = pgserver.get_server(tmp_path / "pg")
        try:
            yield server.get_uri()
        finally:
            server.cleanup()
        return

    schema = f"test_radar_{uuid.uuid4().hex}"
    conn = psycopg2.connect(dsn)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    try:
        yield make_dsn(dsn, options=f"-c search_path={schema}")
    finally:
        with conn.cursor() as cur:
            cur.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
        conn.close()
