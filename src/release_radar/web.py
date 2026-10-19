from __future__ import annotations

import hashlib
import json
import logging
import math
from datetime import UTC, date, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from psycopg2.extras import RealDictCursor

from .dedupe import row_work_key
from .links import link_kind
from .release_policy import release_state
from .web_support import Database, RateLimiter, TTLCache
from .work_identity import classify_video_title

STATIC = Path(__file__).with_name("static")
FILES = {
    "/": ("index.html", "text/html"),
    "/app.css": ("app.css", "text/css"),
    "/app.js": ("app.js", "text/javascript"),
}
logger = logging.getLogger(__name__)
# Ocultar clipes e repetidos exige ler alem de `limit`; le em lotes ate completar a lista.
BATCH_SIZE = 240
MAX_SCANNED_ROWS = 5000
TRAILER_TYPES = {"trailer", "teaser", "announcement"}


def list_releases(dsn: str | Database, limit: int = 120) -> list[dict]:
    db = dsn if isinstance(dsn, Database) else Database(dsn, maxconn=1)
    try:
        items: list[dict] = []
        seen_works: set[str] = set()
        cursor: tuple[object, int] | None = None
        scanned = 0
        while len(items) < limit and scanned < MAX_SCANNED_ROWS:
            rows = fetch_batch(db, cursor)
            if not rows:
                break
            scanned += len(rows)
            for row in rows:
                if len(items) >= limit:
                    break
                item = to_item(row, seen_works)
                if item:
                    items.append(item)
            last = rows[-1]
            if len(rows) < BATCH_SIZE or last["posted_at"] is None:
                break
            cursor = (last["posted_at"], last["id"])
        return items
    finally:
        if db is not dsn:
            db.close()


def fetch_batch(db: Database, cursor: tuple[object, int] | None) -> list[dict]:
    """Proxima pagina (keyset) das publicacoes, da mais recente para a mais antiga."""
    after = "AND (posted_at, id) < (%s, %s)" if cursor else ""
    with db.connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            f"""SELECT id, external_id, source, title, url, channel, category, thumbnail,
                       analysis, analysis_summary, posted_at, work_key
                FROM release_items WHERE status = 'posted' AND posted_at IS NOT NULL {after}
                ORDER BY posted_at DESC, id DESC LIMIT %s""",
            (*(cursor or ()), BATCH_SIZE),
        )
        return cur.fetchall()


def to_item(row: dict, seen_works: set[str]) -> dict | None:
    analysis = row["analysis"] if isinstance(row["analysis"], dict) else {}
    kind = link_kind(row["url"], row["source"])
    content_type = video_content_type(kind, row["title"], analysis)
    if content_type == "clip" or (kind == "video" and not_new_work(row, seen_works)):
        return None
    return {
        "id": row["external_id"],
        "source": row["source"],
        "kind": kind,
        "content_type": content_type,
        "title": analysis.get("title") or row["title"],
        "url": row["url"],
        "channel": row["channel"],
        "category": row["category"],
        "thumbnail": row["thumbnail"],
        "summary": analysis.get("synopsis") or row["analysis_summary"] or "",
        "release_window": analysis.get("release_window") or "A definir",
        "release_date": str(analysis.get("release_date") or ""),
        "availability": release_state(
            str(analysis.get("release_date") or ""),
            str(analysis.get("release_status") or "unknown"),
        ),
        "why_it_matters": analysis.get("why_it_matters") or "",
        "platforms": analysis.get("platforms")
        if isinstance(analysis.get("platforms"), list)
        else [],
        "posted_at": posted_at_utc(row["posted_at"]),
    }


def posted_at_utc(posted: object) -> str | None:
    # TIMESTAMP sem fuso guarda o NOW() do servidor (UTC no deploy); sem offset o navegador erraria.
    if isinstance(posted, datetime):
        return (posted if posted.tzinfo else posted.replace(tzinfo=UTC)).isoformat()
    return posted.isoformat() if isinstance(posted, date) else None


def video_content_type(kind: str, title: str, analysis: dict) -> str:
    """Clipes ja publicados antes do filtro tambem saem do painel; so trailers ficam."""
    if kind != "video":
        return kind
    declared = str(analysis.get("content_type") or "")
    if declared in {"clip", "other"} or classify_video_title(title) == "clip":
        return "clip"
    if declared in TRAILER_TYPES:
        return declared
    return "trailer" if classify_video_title(title) == "trailer" else "video"


def not_new_work(row: dict, seen_works: set[str]) -> bool:
    """True quando outro trailer mais recente da mesma obra ja entrou na lista."""
    key = row_work_key(row)
    if not key:
        return False
    if key in seen_works:
        return True
    seen_works.add(key)
    return False


def create_server(
    dsn: str,
    host: str = "127.0.0.1",
    port: int = 8765,
    *,
    cache_ttl: float = 15.0,
    rate_burst: int = 60,
    rate_per_second: float = 2.0,
) -> ThreadingHTTPServer:
    db = Database(dsn)
    cache: TTLCache[bytes] = TTLCache(ttl=cache_ttl)
    limiter = RateLimiter(burst=rate_burst, per_second=rate_per_second)

    def releases_body() -> bytes:
        return json.dumps({"items": list_releases(db)}, ensure_ascii=False).encode()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            path = urlsplit(self.path).path
            headers: dict[str, str] = {}
            if path == "/api/releases":
                status, body = self.releases(headers)
            elif path == "/healthz":
                status, body = self.health(headers)
            elif path in FILES:
                status, body = self.static(path, headers)
            else:
                self.send_error(404)
                return
            self.send_response(status)
            for name, value in headers.items():
                self.send_header(name, value)
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; img-src 'self' https: data:; "
                "script-src 'self'; style-src 'self'; connect-src 'self'; "
                "base-uri 'none'; frame-ancestors 'none'",
            )
            if status != 304:
                self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if status != 304:
                self.wfile.write(body)

        def releases(self, headers: dict[str, str]) -> tuple[int, bytes]:
            headers["Content-Type"] = "application/json; charset=utf-8"
            headers["Cache-Control"] = "no-store"
            wait = limiter.acquire(self.client_address[0])
            if wait:
                headers["Retry-After"] = str(max(1, math.ceil(wait)))
                return 429, b'{"error":"Muitas requisicoes. Tente novamente em instantes."}'
            try:
                return 200, cache.get_or_load("releases", releases_body)
            except Exception:
                logger.exception("Failed to load releases")
                return 503, b'{"error":"Nao foi possivel carregar os lancamentos."}'

        def health(self, headers: dict[str, str]) -> tuple[int, bytes]:
            headers["Content-Type"] = "application/json; charset=utf-8"
            headers["Cache-Control"] = "no-store"
            try:
                db.ping()
            except Exception:
                logger.exception("Health check failed")
                return 503, b'{"status":"unavailable"}'
            return 200, b'{"status":"ok"}'

        def static(self, path: str, headers: dict[str, str]) -> tuple[int, bytes]:
            filename, mime = FILES[path]
            body = (STATIC / filename).read_bytes()
            etag = f'"{hashlib.sha256(body).hexdigest()[:16]}"'
            headers["Content-Type"] = f"{mime}; charset=utf-8"
            # Revalida a cada uso: um deploy novo aparece na hora, sem baixar o arquivo de novo.
            headers["Cache-Control"] = "no-cache"
            headers["ETag"] = etag
            if etag in (self.headers.get("If-None-Match") or "").split(", "):
                return 304, b""
            return 200, body

        def log_message(self, format: str, *args: object) -> None:
            logger.info("%s %s", self.address_string(), format % args)

    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True
    original_close = server.server_close

    def close() -> None:
        original_close()
        db.close()

    server.server_close = close  # type: ignore[method-assign]
    return server


def serve(dsn: str, host: str = "127.0.0.1", port: int = 8765) -> None:
    server = create_server(dsn, host, port)
    print(f"Painel do Release Radar: http://{host}:{server.server_port}")
    print("Use Ctrl+C para encerrar. O painel mostra os links publicados pelo bot.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
