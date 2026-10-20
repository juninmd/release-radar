from __future__ import annotations

import hashlib
import html
import logging
import re
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree

import httpx

from ..models import ReleaseCandidate
from ..net_guard import assert_public_url
from ..resilience import with_retries

logger = logging.getLogger(__name__)

_TAG_RE = re.compile(r"<[^>]+>")
_IMG_RE = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']', re.IGNORECASE)
_DOCTYPE_RE = re.compile(rb"<!DOCTYPE", re.IGNORECASE)
_MAX_DESCRIPTION = 4000
# xml.etree expande entidades internas: um feed hostil com DTD estoura a memoria
# do job (billion laughs). Feed legitimo nao declara DOCTYPE, entao recusamos.
_MAX_FEED_BYTES = 8 * 1024 * 1024
_DOCTYPE_SCAN_BYTES = 4096
_MAX_REDIRECTS = 5


def fetch_rss(
    client: httpx.Client, feed_url: str, category: str, limit: int
) -> list[ReleaseCandidate]:
    """Itens recentes de um feed RSS 2.0, RDF ou Atom (sem API key)."""
    body = with_retries(lambda: _read_body(client, feed_url), label=f"RSS {feed_url}")
    root = ElementTree.fromstring(body)
    feed_title = _first_text(root, ("channel/title", "title")) or feed_url
    entries = _find_all(root, ("item", "entry"))
    candidates: list[ReleaseCandidate] = []
    for entry in entries[:limit]:
        candidate = _to_candidate(entry, feed_title, category)
        if candidate is not None:
            candidates.append(candidate)
    return candidates


def _read_body(client: httpx.Client, feed_url: str) -> bytes:
    """Le o feed abortando no limite: um corpo infinito nao pode ser bufferizado antes.

    Redirecionamos a mao (o cliente nao segue) para revalidar cada salto: um feed
    publico pode responder 302 apontando para a rede interna (metadados, servicos).
    """
    url = feed_url
    for _ in range(_MAX_REDIRECTS + 1):
        assert_public_url(url)
        with client.stream("GET", url, follow_redirects=False) as response:
            if response.is_redirect:
                location = response.headers.get("location")
                if not location:
                    raise ValueError(f"Feed {url} redirecionou sem Location")
                url = str(response.url.join(location))
                continue
            response.raise_for_status()
            return _drain(response, url)
    raise ValueError(f"Feed {feed_url} redirecionou demais")


def _drain(response: httpx.Response, feed_url: str) -> bytes:
    chunks: list[bytes] = []
    size = 0
    for chunk in response.iter_bytes():
        size += len(chunk)
        if size > _MAX_FEED_BYTES:
            raise ValueError(f"Feed {feed_url} acima de {_MAX_FEED_BYTES} bytes")
        chunks.append(chunk)
    body = b"".join(chunks)
    if _DOCTYPE_RE.search(body[:_DOCTYPE_SCAN_BYTES]):
        raise ValueError(f"Feed {feed_url} declara DOCTYPE; recusado")
    return body


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _find_all(root: ElementTree.Element, names: tuple[str, ...]) -> list[ElementTree.Element]:
    return [node for node in root.iter() if _local(node.tag) in names]


def _child_text(node: ElementTree.Element, name: str) -> str:
    for child in node:
        if _local(child.tag) == name and child.text:
            return child.text.strip()
    return ""


def _first_text(root: ElementTree.Element, paths: tuple[str, ...]) -> str:
    for node in root.iter():
        if _local(node.tag) in ("channel", "feed"):
            text = _child_text(node, "title")
            if text:
                return text
    for path in paths:
        found = root.find(path)
        if found is not None and found.text:
            return found.text.strip()
    return ""


def _link(entry: ElementTree.Element) -> str:
    text = _child_text(entry, "link")
    if text:
        return text
    for child in entry:
        if _local(child.tag) == "link":
            href = child.attrib.get("href")
            if href:
                return href
    return _child_text(entry, "guid")


def _is_http_url(value: str | None) -> bool:
    return bool(value) and str(value).startswith(("http://", "https://"))


def _thumbnail(entry: ElementTree.Element, description_html: str) -> str | None:
    """So aceita imagem http(s) absoluta.

    Telegram rejeita URL relativa/nao-imagem em send_photo, e a falha e engolida
    pelo publisher: o item ficaria analisado e nunca publicado, sem retry.
    """
    for child in entry:
        if _local(child.tag) not in ("thumbnail", "content", "enclosure"):
            continue
        url = child.attrib.get("url")
        media_type = child.attrib.get("type", "image")
        if _is_http_url(url) and media_type.startswith("image"):
            return url
    match = _IMG_RE.search(description_html)
    if match and _is_http_url(match.group(1)):
        return match.group(1)
    return None


def _published(entry: ElementTree.Element) -> str | None:
    """pubDate RFC-822 ou date/updated ISO -> YYYYMMDD, formato usado na ordenacao."""
    raw = _child_text(entry, "pubDate")
    if raw:
        try:
            return parsedate_to_datetime(raw).strftime("%Y%m%d")
        except (TypeError, ValueError):
            logger.debug("Unparsable pubDate: %s", raw)
    for name in ("published", "updated", "date"):
        iso = _child_text(entry, name)
        if len(iso) >= 10:
            return iso[:10].replace("-", "")
    return None


def _strip_html(value: str) -> str:
    text = html.unescape(_TAG_RE.sub(" ", value))
    return re.sub(r"[ \t]+", " ", text).strip()


def _to_candidate(
    entry: ElementTree.Element, feed_title: str, category: str
) -> ReleaseCandidate | None:
    link = _link(entry)
    title = _child_text(entry, "title")
    # guid nem sempre e permalink ("urn:uuid:..."), e essa url vai para o banco
    # (coluna UNIQUE) e para o link do Telegram.
    if not _is_http_url(link) or not title:
        return None
    body_html = _child_text(entry, "description") or _child_text(entry, "encoded")
    summary = _child_text(entry, "summary") or _child_text(entry, "content")
    identity = _child_text(entry, "guid") or link
    return ReleaseCandidate(
        external_id=f"rss:{hashlib.sha256(identity.encode('utf-8')).hexdigest()[:24]}",
        title=_strip_html(title),
        url=link,
        channel=_strip_html(feed_title),
        category=category,
        duration=0,
        upload_date=_published(entry),
        thumbnail=_thumbnail(entry, body_html),
        description=_strip_html(f"{body_html}\n{summary}")[:_MAX_DESCRIPTION],
        source="rss",
    )
