from __future__ import annotations

import logging
import math
import random
import time
from collections.abc import Callable
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import TypeVar

import httpx

logger = logging.getLogger(__name__)

T = TypeVar("T")

RETRYABLE_STATUS = frozenset({408, 425, 429, 500, 502, 503, 504})
MAX_RETRY_AFTER = 10.0


def is_transient(exc: BaseException) -> bool:
    """Falhas que valem uma nova tentativa: rede, timeout, 429 e 5xx."""
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in RETRYABLE_STATUS
    return isinstance(exc, httpx.TransportError)


def retry_after_seconds(exc: BaseException) -> float | None:
    if not isinstance(exc, httpx.HTTPStatusError):
        return None
    header_val = exc.response.headers.get("Retry-After")
    if header_val is None:
        return None

    header_val = header_val.strip()
    try:
        v = float(header_val)
        if math.isfinite(v) and v >= 0:
            return min(v, MAX_RETRY_AFTER)
        return None
    except ValueError:
        pass

    try:
        dt = parsedate_to_datetime(header_val)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        now = datetime.now(UTC)
        diff = (dt - now).total_seconds()
        return min(max(0.0, diff), MAX_RETRY_AFTER)
    except Exception:
        return None


def with_retries(
    call: Callable[[], T],
    *,
    attempts: int = 3,
    base_delay: float = 0.5,
    max_delay: float = 8.0,
    label: str = "request",
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    """Repete `call` com backoff exponencial e jitter apenas para falhas transitorias."""
    for attempt in range(1, attempts + 1):
        try:
            return call()
        except Exception as exc:
            if attempt == attempts or not is_transient(exc):
                raise
            delay = retry_after_seconds(exc)
            if delay is None:
                delay = min(base_delay * 2 ** (attempt - 1), max_delay)
                delay += random.uniform(0, delay / 4)
            delay = max(0.0, delay)
            logger.warning(
                "%s failed (%s); retry %s/%s in %.1fs",
                label,
                exc.__class__.__name__,
                attempt,
                attempts - 1,
                delay,
            )
            sleep(delay)
    raise AssertionError("unreachable")  # pragma: no cover


def get_json(client: httpx.Client, url: str, **kwargs) -> dict:
    """GET com retry que devolve o JSON; levanta HTTPStatusError em resposta final ruim."""

    def call() -> dict:
        response = client.get(url, **kwargs)
        response.raise_for_status()
        return response.json()

    return with_retries(call, label=f"GET {url}")


def post_json(client: httpx.Client, url: str, **kwargs) -> dict:
    """POST com retry que devolve o JSON (GraphQL); levanta HTTPStatusError se falhar."""

    def call() -> dict:
        response = client.post(url, **kwargs)
        response.raise_for_status()
        return response.json()

    return with_retries(call, label=f"POST {url}")


class CircuitBreaker:
    """Abre apos N falhas seguidas e so volta a tentar depois do cooldown.

    Evita que um servico fora do ar (Whisper, LLM) consuma o timeout inteiro a cada item
    de uma rodada. Qualquer sucesso fecha o circuito de novo.
    """

    def __init__(
        self,
        name: str,
        threshold: int = 3,
        cooldown: float = 300.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.name = name
        self.threshold = threshold
        self.cooldown = cooldown
        self._clock = clock
        self._failures = 0
        self._opened_at: float | None = None

    @property
    def is_open(self) -> bool:
        if self._opened_at is None:
            return False
        if self._clock() - self._opened_at >= self.cooldown:
            # Meia-abertura: permite uma tentativa; outra falha reabre na hora.
            self._opened_at = None
            self._failures = self.threshold - 1
            return False
        return True

    def record_success(self) -> None:
        self._failures = 0
        self._opened_at = None

    def record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self.threshold and self._opened_at is None:
            self._opened_at = self._clock()
            logger.error(
                "Circuit '%s' opened after %s consecutive failures; pausing for %.0fs",
                self.name,
                self._failures,
                self.cooldown,
            )
