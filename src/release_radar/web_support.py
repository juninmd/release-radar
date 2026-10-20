from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Generic, TypeVar

import psycopg2
from psycopg2.pool import ThreadedConnectionPool

logger = logging.getLogger(__name__)

T = TypeVar("T")


class Database:
    """Pool pequeno e preguicoso: o painel reaproveita conexoes em vez de abrir uma por request."""

    def __init__(self, dsn: str, maxconn: int = 4, acquire_timeout: float = 5.0) -> None:
        self._dsn = dsn
        self._maxconn = maxconn
        self._acquire_timeout = acquire_timeout
        self._pool: ThreadedConnectionPool | None = None
        self._lock = threading.Lock()
        # O pool do psycopg2 levanta erro quando esgota; o semaforo faz o request esperar.
        self._slots = threading.BoundedSemaphore(maxconn)

    def _ensure_pool(self) -> ThreadedConnectionPool:
        with self._lock:
            if self._pool is None:
                self._pool = ThreadedConnectionPool(1, self._maxconn, self._dsn, connect_timeout=10)
            return self._pool

    @contextmanager
    def connection(self) -> Iterator[psycopg2.extensions.connection]:
        if not self._slots.acquire(timeout=self._acquire_timeout):
            raise TimeoutError("Sem conexao livre com o banco")
        try:
            pool = self._ensure_pool()
            conn = pool.getconn()
            broken = False
            try:
                yield conn
            except (psycopg2.OperationalError, psycopg2.InterfaceError):
                broken = True
                raise
            finally:
                if not broken and not conn.closed:
                    conn.rollback()  # encerra a transacao de leitura antes de devolver
                pool.putconn(conn, close=broken or bool(conn.closed))
        finally:
            self._slots.release()

    def ping(self) -> None:
        with self.connection() as conn, conn.cursor() as cur:
            cur.execute("SELECT 1")

    def close(self) -> None:
        with self._lock:
            if self._pool is not None:
                self._pool.closeall()
                self._pool = None


class TTLCache(Generic[T]):
    """Cache de um valor por chave com single-flight e fallback para o ultimo valor bom.

    - Dentro do `ttl`, requests repetidos nao tocam o banco.
    - Se varios requests chegam com o cache vencido, so um recarrega; os outros esperam.
    - Se a recarga falha, serve o valor anterior ate `stale_ttl` (melhor dado velho que 503).
    """

    def __init__(
        self,
        ttl: float = 15.0,
        stale_ttl: float = 300.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._ttl = ttl
        self._stale_ttl = stale_ttl
        self._clock = clock
        self._lock = threading.Lock()
        self._entries: dict[object, tuple[float, T]] = {}

    def get_or_load(self, key: object, loader: Callable[[], T]) -> T:
        with self._lock:
            now = self._clock()
            entry = self._entries.get(key)
            if entry and now - entry[0] < self._ttl:
                return entry[1]
            try:
                value = loader()
            except Exception:
                if entry and now - entry[0] < self._stale_ttl:
                    logger.warning("Reload failed; serving stale cache", exc_info=True)
                    return entry[1]
                raise
            self._entries[key] = (self._clock(), value)
            return value


class RateLimiter:
    """Token bucket por cliente. `burst` requests de uma vez, repondo `per_second` por segundo."""

    MAX_CLIENTS = 2048

    def __init__(
        self,
        burst: int = 60,
        per_second: float = 2.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._burst = burst
        self._per_second = per_second
        self._clock = clock
        self._lock = threading.Lock()
        self._buckets: dict[str, tuple[float, float]] = {}

    def acquire(self, client: str) -> float:
        """0.0 quando liberado; senao, segundos ate haver credito."""
        with self._lock:
            now = self._clock()
            tokens, last = self._buckets.get(client, (float(self._burst), now))
            tokens = min(self._burst, tokens + (now - last) * self._per_second)
            if tokens < 1.0:
                self._buckets[client] = (tokens, now)
                return (1.0 - tokens) / self._per_second
            self._buckets[client] = (tokens - 1.0, now)
            if len(self._buckets) > self.MAX_CLIENTS:
                self._prune(now)
            return 0.0

    def _prune(self, now: float) -> None:
        idle = self._burst / self._per_second
        self._buckets = {k: v for k, v in self._buckets.items() if now - v[1] < idle}
