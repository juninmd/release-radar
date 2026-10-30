from __future__ import annotations

from typing import Any

import psycopg2

from release_radar import db, dedupe, settings_store


class FakeCursor:
    def __init__(self, rows: list[Any] | None = None, row: Any = None):
        self._rows = rows or []
        self._row = row

    def __enter__(self) -> FakeCursor:
        return self

    def __exit__(self, *exc: object) -> bool:
        return False

    def execute(self, *args: object, **kwargs: object) -> None:
        return None

    def fetchone(self) -> Any:
        return self._row

    def fetchall(self) -> list[Any]:
        return self._rows


class FakeConnection:
    """Conexao minima: o teste garante que leituras fecham a transacao."""

    def __init__(self, row: Any = None, rows: list[Any] | None = None):
        self._row = row
        self._rows = rows or []
        self.commits = 0

    def cursor(self, **kwargs: object) -> FakeCursor:
        return FakeCursor(rows=self._rows, row=self._row)

    def commit(self) -> None:
        self.commits += 1


def test_get_item_commits_the_read_transaction() -> None:
    conn = FakeConnection(row={"external_id": "abc"})

    assert db.get_item(conn, "abc") == {"external_id": "abc"}
    assert conn.commits == 1


def test_get_item_commits_even_when_missing() -> None:
    conn = FakeConnection(row=None)

    assert db.get_item(conn, "missing") is None
    assert conn.commits == 1


def test_work_already_posted_commits_the_read_transaction() -> None:
    conn = FakeConnection(row=(1,))

    assert dedupe.work_already_posted(conn, ["obra"]) is True
    assert conn.commits == 1


def test_read_overrides_commits_the_read_transaction() -> None:
    conn = FakeConnection(rows=[{"key": "max_items_per_run", "value": 5}])

    # A chave nao esta em EDITABLE_FIELDS: o valor e descartado, mas a transacao
    # do SELECT precisa ser fechada.
    settings_store.read_overrides(conn)
    assert conn.commits == 1


class DeadConnection(FakeConnection):
    def cursor(self, **kwargs: object) -> FakeCursor:
        raise psycopg2.OperationalError("server closed the connection unexpectedly")

    def close(self) -> None:
        return None


def test_ensure_connection_reconnects_after_lost_session(monkeypatch) -> None:
    sentinel = object()
    monkeypatch.setattr(db, "get_connection", lambda dsn: sentinel)

    assert db.ensure_connection(DeadConnection(), "postgresql://db") is sentinel


def test_ensure_connection_keeps_a_healthy_connection() -> None:
    conn = FakeConnection()

    assert db.ensure_connection(conn, "postgresql://db") is conn
    assert conn.commits == 1
