from __future__ import annotations

import httpx
import pytest

from release_radar.resilience import CircuitBreaker, get_json, with_retries
from release_radar.web_support import RateLimiter, TTLCache


def status_error(code: int, headers: dict[str, str] | None = None) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "https://example.test")
    return httpx.HTTPStatusError(
        "boom", request=request, response=httpx.Response(code, headers=headers, request=request)
    )


def test_retries_transient_failures_then_succeeds() -> None:
    calls, sleeps = [], []

    def flaky() -> str:
        calls.append(1)
        if len(calls) < 3:
            raise httpx.ConnectTimeout("lento")
        return "ok"

    assert with_retries(flaky, sleep=sleeps.append) == "ok"
    assert len(calls) == 3
    assert len(sleeps) == 2 and sleeps[1] > sleeps[0] * 1.2  # backoff exponencial


def test_gives_up_after_the_last_attempt() -> None:
    calls = []

    def always_down() -> None:
        calls.append(1)
        raise status_error(503)

    with pytest.raises(httpx.HTTPStatusError):
        with_retries(always_down, attempts=3, sleep=lambda _: None)
    assert len(calls) == 3


@pytest.mark.parametrize("code", [400, 401, 403, 404])
def test_client_errors_are_not_retried(code: int) -> None:
    calls = []

    def bad_request() -> None:
        calls.append(1)
        raise status_error(code)

    with pytest.raises(httpx.HTTPStatusError):
        with_retries(bad_request, sleep=lambda _: None)
    assert len(calls) == 1


def test_non_http_errors_are_not_retried() -> None:
    calls = []

    def broken() -> None:
        calls.append(1)
        raise ValueError("feed invalido")

    with pytest.raises(ValueError):
        with_retries(broken, sleep=lambda _: None)
    assert len(calls) == 1


def test_retry_after_header_is_honored_and_capped() -> None:
    sleeps = []
    attempts = iter(
        [status_error(429, {"Retry-After": "3"}), status_error(429, {"Retry-After": "999"})]
    )

    def limited() -> str:
        try:
            raise next(attempts)
        except StopIteration:
            return "ok"

    assert with_retries(limited, attempts=3, sleep=sleeps.append) == "ok"
    assert sleeps == [3.0, 10.0]


@pytest.mark.parametrize("invalid_header", ["-1", "nan", "inf", "-inf", "abc"])
def test_retry_after_invalid_or_negative_falls_back_to_backoff(invalid_header: str) -> None:
    sleeps = []
    attempts = iter([status_error(429, {"Retry-After": invalid_header})])

    def limited() -> str:
        try:
            raise next(attempts)
        except StopIteration:
            return "ok"

    assert with_retries(limited, attempts=2, base_delay=1.0, sleep=sleeps.append) == "ok"
    assert len(sleeps) == 1
    # Falls back to standard backoff (base_delay 1.0 + jitter)
    assert 1.0 <= sleeps[0] <= 1.25


def test_retry_after_zero_and_valid_seconds() -> None:
    sleeps = []
    attempts = iter(
        [status_error(429, {"Retry-After": "0"}), status_error(429, {"Retry-After": "3"})]
    )

    def limited() -> str:
        try:
            raise next(attempts)
        except StopIteration:
            return "ok"

    assert with_retries(limited, attempts=3, sleep=sleeps.append) == "ok"
    assert sleeps == [0.0, 3.0]


def test_retry_after_http_date() -> None:
    from datetime import UTC, datetime, timedelta
    from email.utils import format_datetime

    future_dt = datetime.now(UTC) + timedelta(seconds=5)
    past_dt = datetime.now(UTC) - timedelta(seconds=10)

    sleeps = []
    attempts = iter(
        [
            status_error(429, {"Retry-After": format_datetime(future_dt)}),
            status_error(429, {"Retry-After": format_datetime(past_dt)}),
        ]
    )

    def limited() -> str:
        try:
            raise next(attempts)
        except StopIteration:
            return "ok"

    assert with_retries(limited, attempts=3, sleep=sleeps.append) == "ok"
    assert len(sleeps) == 2
    assert 0.0 <= sleeps[0] <= 5.0
    assert sleeps[1] == 0.0


def test_get_json_retries_5xx_responses() -> None:
    responses = [httpx.Response(502), httpx.Response(200, json={"ok": True})]

    def handler(request: httpx.Request) -> httpx.Response:
        return responses.pop(0)

    import release_radar.resilience as resilience

    original = resilience.time.sleep
    resilience.time.sleep = lambda _: None
    try:
        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            assert get_json(client, "https://example.test/api") == {"ok": True}
    finally:
        resilience.time.sleep = original


def test_circuit_breaker_opens_after_threshold_and_recovers_after_cooldown() -> None:
    now = [0.0]
    breaker = CircuitBreaker("llm", threshold=2, cooldown=60, clock=lambda: now[0])

    breaker.record_failure()
    assert not breaker.is_open
    breaker.record_failure()
    assert breaker.is_open

    now[0] = 61
    assert not breaker.is_open  # meia-abertura: uma tentativa
    breaker.record_failure()
    assert breaker.is_open  # falhou de novo, reabre na hora

    now[0] = 130
    assert not breaker.is_open
    breaker.record_success()
    breaker.record_failure()
    assert not breaker.is_open  # sucesso zera a contagem


def test_ttl_cache_loads_once_within_ttl_and_reloads_after() -> None:
    now = [0.0]
    cache: TTLCache[int] = TTLCache(ttl=10, clock=lambda: now[0])
    values = iter(range(100))

    assert cache.get_or_load("k", lambda: next(values)) == 0
    assert cache.get_or_load("k", lambda: next(values)) == 0
    now[0] = 11
    assert cache.get_or_load("k", lambda: next(values)) == 1


def test_ttl_cache_serves_stale_value_when_reload_fails_until_stale_limit() -> None:
    now = [0.0]
    cache: TTLCache[str] = TTLCache(ttl=10, stale_ttl=100, clock=lambda: now[0])
    cache.get_or_load("k", lambda: "bom")

    def fail() -> str:
        raise RuntimeError("banco fora")

    now[0] = 50
    assert cache.get_or_load("k", fail) == "bom"
    now[0] = 101
    with pytest.raises(RuntimeError):
        cache.get_or_load("k", fail)


def test_rate_limiter_blocks_after_burst_and_refills() -> None:
    now = [0.0]
    limiter = RateLimiter(burst=2, per_second=1, clock=lambda: now[0])

    assert limiter.acquire("a") == 0
    assert limiter.acquire("a") == 0
    assert limiter.acquire("a") == pytest.approx(1.0)
    assert limiter.acquire("b") == 0  # cota por cliente
    now[0] = 1.0
    assert limiter.acquire("a") == 0
