from __future__ import annotations

import httpx
import pytest

from release_radar.net_guard import InternalTargetError, assert_public_url, is_internal_host
from release_radar.sources.rss import _read_body


@pytest.mark.parametrize(
    "host",
    [
        "localhost",
        "localhost.",
        "127.0.0.1",
        "[::1]",
        "10.0.0.5",
        "192.168.0.1",
        "169.254.169.254",
        "metadata.google.internal",
        "db.internal",
        "litellm.ai.svc.cluster.local",
        "127.1",
        "2130706433",
        "0x7f000001",
        "0177.0.0.1",
        "::ffff:127.0.0.1",
    ],
)
def test_internal_hosts_are_blocked(host: str) -> None:
    assert is_internal_host(host) is True


@pytest.mark.parametrize("host", ["example.test", "blog.playstation.com", "8.8.8.8"])
def test_public_hosts_are_allowed(host: str) -> None:
    assert is_internal_host(host) is False


@pytest.mark.parametrize(
    "url",
    [
        "ftp://example.test/feed",
        "example.test/feed",
        "http://169.254.169.254/latest/meta-data/",
        "http://[::ffff:127.0.0.1]/feed",
        "http://2130706433/feed",
    ],
)
def test_assert_public_url_rejects_internal_targets(url: str) -> None:
    with pytest.raises(InternalTargetError):
        assert_public_url(url)


def test_assert_public_url_accepts_a_public_feed() -> None:
    assert assert_public_url("https://blog.playstation.com/feed/") == (
        "https://blog.playstation.com/feed/"
    )


def test_rss_refuses_a_redirect_into_the_internal_network() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "http://169.254.169.254/latest/meta-data/"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(InternalTargetError):
        _read_body(client, "https://feeds.example.test/rss")


def test_rss_follows_a_public_redirect() -> None:
    feed = b"<rss><channel><title>Feed</title></channel></rss>"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/old":
            return httpx.Response(301, headers={"location": "https://feeds.example.test/new"})
        return httpx.Response(200, content=feed, headers={"content-type": "application/rss+xml"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    assert _read_body(client, "https://feeds.example.test/old").startswith(b"<rss>")
