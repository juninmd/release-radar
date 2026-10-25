from __future__ import annotations

import httpx

from release_radar.sources.rss import fetch_rss

RSS_2_0 = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/">
  <channel>
    <title>PlayStation.Blog</title>
    <item>
      <title>Saga X &amp;mdash; trailer de lancamento</title>
      <link>https://blog.playstation.com/saga-x/</link>
      <guid>https://blog.playstation.com/?p=1</guid>
      <pubDate>Mon, 07 Sep 2026 13:00:05 +0000</pubDate>
      <description>&lt;p&gt;Chega em &lt;b&gt;2027&lt;/b&gt;&lt;/p&gt;&lt;img src="https://cdn/x.jpg"/&gt;</description>
    </item>
    <item>
      <title>Sem link</title>
    </item>
  </channel>
</rss>
"""

ATOM = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Xbox Wire</title>
  <entry>
    <title>Jogo Y anunciado</title>
    <link rel="alternate" href="https://news.xbox.com/jogo-y/"/>
    <updated>2026-09-06T10:00:00Z</updated>
    <summary>Chega no Game Pass</summary>
  </entry>
</feed>
"""


def client_for(body: str) -> httpx.Client:
    transport = httpx.MockTransport(lambda request: httpx.Response(200, text=body))
    return httpx.Client(transport=transport)


def test_rss_2_0_item_becomes_candidate() -> None:
    with client_for(RSS_2_0) as client:
        candidates = fetch_rss(client, "https://feed", category="games", limit=10)

    # O item sem link e descartado; so o primeiro vira candidato.
    assert len(candidates) == 1
    item = candidates[0]
    assert item.source == "rss"
    assert item.external_id.startswith("rss:")
    assert item.category == "games"
    assert item.channel == "PlayStation.Blog"
    assert item.url == "https://blog.playstation.com/saga-x/"
    assert item.upload_date == "20260907"
    assert item.thumbnail == "https://cdn/x.jpg"
    assert "Chega em 2027" in item.description
    assert "<b>" not in item.description


def test_rss_limit_is_respected() -> None:
    with client_for(RSS_2_0) as client:
        assert fetch_rss(client, "https://feed", category="games", limit=1) != []


def test_atom_entry_uses_link_href_and_iso_date() -> None:
    with client_for(ATOM) as client:
        candidates = fetch_rss(client, "https://feed", category="games", limit=10)

    assert len(candidates) == 1
    item = candidates[0]
    assert item.url == "https://news.xbox.com/jogo-y/"
    assert item.upload_date == "20260906"
    assert item.channel == "Xbox Wire"


def test_same_guid_produces_stable_id() -> None:
    with client_for(RSS_2_0) as client:
        first = fetch_rss(client, "https://feed", category="games", limit=10)[0]
    with client_for(RSS_2_0) as client:
        second = fetch_rss(client, "https://feed", category="movies", limit=10)[0]

    assert first.external_id == second.external_id


BILLION_LAUGHS = """<?xml version="1.0"?>
<!DOCTYPE lolz [<!ENTITY lol "lol"><!ENTITY lol2 "&lol;&lol;&lol;&lol;">]>
<rss version="2.0"><channel><title>x</title>
<item><title>&lol2;</title><link>http://x</link></item></channel></rss>
"""


def test_feed_with_doctype_is_refused() -> None:
    # xml.etree expande entidades internas; recusar DTD evita estourar a memoria.
    with client_for(BILLION_LAUGHS) as client:
        try:
            fetch_rss(client, "https://feed", category="games", limit=5)
        except ValueError as error:
            assert "DOCTYPE" in str(error)
        else:  # pragma: no cover - falha explicita
            raise AssertionError("feed com DOCTYPE deveria ser recusado")


def test_feed_with_large_comment_before_doctype_is_refused() -> None:
    body = (
        b'<?xml version="1.0"?><!-- '
        + b"a" * 5000
        + b' --><!DOCTYPE r [<!ENTITY a "x">]><r>&a;</r>'
    )
    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=body))
    with httpx.Client(transport=transport) as client:
        try:
            fetch_rss(client, "https://feed", category="games", limit=5)
        except ValueError as error:
            assert "declara DOCTYPE; recusado" in str(error)
        else:  # pragma: no cover - falha explicita
            raise AssertionError("feed com comentario longo antes de DOCTYPE deveria ser recusado")


def test_utf16_feed_with_doctype_is_refused() -> None:
    body = '<?xml version="1.0" encoding="utf-16"?><!DOCTYPE r [<!ENTITY a "x">]><r>&a;</r>'.encode(
        "utf-16"
    )
    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=body))
    with httpx.Client(transport=transport) as client:
        try:
            fetch_rss(client, "https://feed", category="games", limit=5)
        except ValueError as error:
            assert "declara DOCTYPE; recusado" in str(error)
        else:  # pragma: no cover - falha explicita
            raise AssertionError("feed UTF-16 com DOCTYPE deveria ser recusado")


def test_oversized_feed_is_refused() -> None:
    huge = "<rss><channel><title>x</title></channel></rss>" + " " * (9 * 1024 * 1024)
    with client_for(huge) as client:
        try:
            fetch_rss(client, "https://feed", category="games", limit=5)
        except ValueError as error:
            assert "bytes" in str(error)
        else:  # pragma: no cover - falha explicita
            raise AssertionError("feed gigante deveria ser recusado")


RELATIVE_ASSETS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/">
  <channel>
    <title>Feed WP</title>
    <item>
      <title>Post com imagem relativa</title>
      <link>https://wp.test/post/</link>
      <description>&lt;img src="/wp-content/pixel.gif"/&gt;texto</description>
    </item>
    <item>
      <title>Post com media video</title>
      <link>https://wp.test/post-2/</link>
      <media:content url="https://wp.test/clip.mp4" type="video/mp4"/>
      <description>texto</description>
    </item>
    <item>
      <title>Item so com guid nao-permalink</title>
      <guid isPermaLink="false">12345</guid>
    </item>
  </channel>
</rss>
"""


def test_relative_and_non_image_thumbnails_are_dropped() -> None:
    # Telegram falha em send_photo com URL relativa e o publisher engole o erro,
    # deixando o item analisado e nunca publicado.
    with client_for(RELATIVE_ASSETS) as client:
        candidates = fetch_rss(client, "https://feed", category="movies", limit=10)

    assert [item.thumbnail for item in candidates] == [None, None]


def test_entry_without_http_link_is_dropped() -> None:
    with client_for(RELATIVE_ASSETS) as client:
        urls = [item.url for item in fetch_rss(client, "https://feed", category="movies", limit=10)]

    assert urls == ["https://wp.test/post/", "https://wp.test/post-2/"]
