"""Migracao e dedupe contra um PostgreSQL real.

Pula quando `pgserver` nao esta instalado:
`uv run --with pgserver pytest tests/test_db_migration.py`.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from release_radar.db import get_connection, get_item, init_db, mark_posted, reserve_candidate
from release_radar.models import ReleaseCandidate

# Schema anterior as fontes nao-YouTube, com uma linha ja publicada.
LEGACY_SCHEMA = """
CREATE TABLE release_items (
    id BIGSERIAL PRIMARY KEY,
    youtube_id TEXT NOT NULL UNIQUE,
    content_hash TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL, url TEXT NOT NULL UNIQUE, channel TEXT NOT NULL,
    category TEXT NOT NULL, duration INTEGER NOT NULL DEFAULT 0,
    upload_date TEXT, thumbnail TEXT, description TEXT DEFAULT '',
    transcript TEXT DEFAULT '', analysis JSONB DEFAULT '{}'::jsonb,
    analysis_summary TEXT DEFAULT '', is_release_signal BOOLEAN DEFAULT FALSE,
    status TEXT NOT NULL DEFAULT 'discovered', posted_at TIMESTAMP,
    skipped_reason TEXT DEFAULT '', created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE TABLE release_events (
    id BIGSERIAL PRIMARY KEY, youtube_id TEXT NOT NULL, event_type TEXT NOT NULL,
    detail JSONB DEFAULT '{}'::jsonb, created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_release_events_youtube_id ON release_events(youtube_id);
INSERT INTO release_items (youtube_id, content_hash, title, url, channel, category, status)
VALUES ('legacyVid', 'hash-legacy', 'Trailer antigo', 'https://youtu.be/legacyVid',
        'Canal', 'movies', 'posted');
INSERT INTO release_events (youtube_id, event_type) VALUES ('legacyVid', 'telegram_posted');
"""


@pytest.fixture
def legacy_dsn(postgres_dsn: str) -> Iterator[str]:
    dsn = postgres_dsn
    conn = get_connection(dsn)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(LEGACY_SCHEMA)
    conn.close()
    yield dsn


def steam_candidate() -> ReleaseCandidate:
    return ReleaseCandidate(
        external_id="steam:3219630",
        title="Halloween: The Game",
        url="https://store.steampowered.com/app/3219630/",
        channel="Steam",
        category="games",
        duration=0,
        upload_date="20260908",
        thumbnail="https://cdn.test/header.jpg",
        description="descricao",
        source="steam",
    )


def test_migration_preserves_posted_rows_and_is_idempotent(legacy_dsn: str) -> None:
    init_db(legacy_dsn)
    init_db(legacy_dsn)

    conn = get_connection(legacy_dsn)
    try:
        row = get_item(conn, "legacyVid")
        assert row is not None
        assert row["status"] == "posted"
        assert row["source"] == "youtube"
    finally:
        conn.close()


def test_already_posted_youtube_item_is_not_reserved_again(legacy_dsn: str) -> None:
    init_db(legacy_dsn)
    conn = get_connection(legacy_dsn)
    try:
        legacy = ReleaseCandidate(
            external_id="legacyVid",
            title="Trailer antigo",
            url="https://youtu.be/legacyVid",
            channel="Canal",
            category="movies",
            duration=90,
            upload_date="20250101",
            thumbnail=None,
        )

        assert reserve_candidate(conn, legacy, "hash-legacy") is False
    finally:
        conn.close()


def test_new_source_is_stored_once_with_its_source(legacy_dsn: str) -> None:
    init_db(legacy_dsn)
    conn = get_connection(legacy_dsn)
    try:
        candidate = steam_candidate()

        assert reserve_candidate(conn, candidate, "hash-steam") is True
        assert reserve_candidate(conn, candidate, "hash-steam") is False

        mark_posted(conn, candidate.external_id)
        stored = get_item(conn, candidate.external_id)
        assert stored is not None
        assert (stored["source"], stored["status"]) == ("steam", "posted")
    finally:
        conn.close()


def test_legacy_event_index_is_renamed_not_duplicated(legacy_dsn: str) -> None:
    init_db(legacy_dsn)
    conn = get_connection(legacy_dsn)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT indexname FROM pg_indexes "
                "WHERE schemaname = current_schema() "
                "AND tablename = 'release_events' AND indexname LIKE 'idx_%'"
            )
            indexes = sorted(row[0] for row in cur.fetchall())

        assert indexes == ["idx_release_events_external_id"]
    finally:
        conn.close()


def test_migrations_are_recorded_once_and_not_reapplied(postgres_dsn: str) -> None:
    from release_radar.migrations import apply_migrations, discover_migrations

    expected = [version for version, _ in discover_migrations()]
    init_db(postgres_dsn)
    conn = get_connection(postgres_dsn)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT version FROM schema_migrations ORDER BY version")
            assert [row[0] for row in cur.fetchall()] == expected
        assert apply_migrations(conn) == []
    finally:
        conn.close()


def test_failed_migration_rolls_back_and_is_not_recorded(postgres_dsn: str, tmp_path) -> None:
    from release_radar.migrations import apply_migrations

    (tmp_path / "0001_ok.sql").write_text("CREATE TABLE ok_table (id INT);")
    (tmp_path / "0002_bad.sql").write_text("CREATE TABLE half (id INT); SELECT boom();")
    conn = get_connection(postgres_dsn)
    try:
        with pytest.raises(Exception, match="boom"):
            apply_migrations(conn, tmp_path)
        with conn.cursor() as cur:
            cur.execute("SELECT version FROM schema_migrations")
            assert [row[0] for row in cur.fetchall()] == ["0001"]
            cur.execute("SELECT to_regclass('half')")
            assert cur.fetchone()[0] is None
    finally:
        conn.close()


def test_invalid_migration_name_is_rejected(tmp_path) -> None:
    from release_radar.migrations import discover_migrations

    (tmp_path / "fix.sql").write_text("SELECT 1;")
    with pytest.raises(ValueError, match="nome invalido"):
        discover_migrations(tmp_path)
