import pytest

from release_radar.links import link_kind


@pytest.mark.parametrize(
    ("url", "source", "kind"),
    [
        ("https://youtu.be/abc", "rss", "video"),
        ("https://www.youtube.com/watch?v=abc", "rss", "video"),
        ("https://youtube.com.fake.test/article", "rss", "article"),
        ("https://store.steampowered.com/app/1", "steam", "catalog"),
    ],
)
def test_link_destination_decides_kind(url: str, source: str, kind: str) -> None:
    assert link_kind(url, source) == kind
