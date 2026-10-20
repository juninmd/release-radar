"""Rodada do bot disparada pelo painel/app desktop, em segundo plano.

A rodada e longa (downloads e transcricao), entao a API nao pode bloquear o
requisicao. Um unico job roda por vez; os demais recebem a rodada em andamento.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any

from .config import Settings
from .pipeline import run_sync

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(UTC).isoformat()


class RunJob:
    """Estado em memoria: nao sobrevive a um reinicio do painel."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state: dict[str, Any] = {
            "running": False,
            "dry_run": False,
            "limit": None,
            "started_at": None,
            "finished_at": None,
            "stats": None,
            "error": None,
        }

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._state)

    def start(
        self, settings: Settings, *, dry_run: bool, limit: int | None, dsn: str | None = None
    ) -> bool:
        """Retorna False quando uma rodada ja esta em andamento."""
        with self._lock:
            if self._state["running"]:
                return False
            self._state.update(
                running=True,
                dry_run=dry_run,
                limit=limit,
                started_at=_now(),
                finished_at=None,
                stats=None,
                error=None,
            )
            thread = threading.Thread(
                target=self._run, args=(settings, dry_run, limit, dsn), daemon=True
            )
            thread.start()
            return True

    def _run(self, settings: Settings, dry_run: bool, limit: int | None, dsn: str | None) -> None:
        try:
            stats = run_sync(settings, limit=limit, dry_run=dry_run, dsn=dsn)
            with self._lock:
                self._state["stats"] = asdict(stats)
        except Exception:  # noqa: BLE001 - a API devolve uma mensagem generica
            logger.exception("Run job failed")
            with self._lock:
                self._state["error"] = "A rodada falhou. Veja os logs do painel."
        finally:
            with self._lock:
                self._state["running"] = False
                self._state["finished_at"] = _now()

    def wait(self, timeout: float | None = None) -> bool:
        """Aguarda o fim da rodada; usado pelos testes. Retorna True se terminou."""
        deadline = None if timeout is None else time.monotonic() + timeout
        while self.snapshot()["running"]:
            if deadline is not None and time.monotonic() >= deadline:
                return False
            time.sleep(0.01)
        return True
