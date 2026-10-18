from __future__ import annotations

import json
import logging
from datetime import UTC, date, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from psycopg2.extras import RealDictCursor

from .db import get_connection
from .dedupe import row_work_key
from .links import link_kind
from .release_policy import release_state
from .work_identity import classify_video_title

STATIC = Path(__file__).with_name("static")
FILES = {
    "/": ("index.html", "text/html"),
    "/app.css": ("app.css", "text/css"),
    "/app.js": ("app.js", "text/javascript"),
}
logger = logging.getLogger(__name__)
# Linhas extras para que ocultar clipes e repetidos ainda deixe `limit` itens visiveis.
OVERFETCH = 4
TRAILER_TYPES = {"trailer", "teaser", "announcement"}


def list_releases(dsn: str, limit: int = 120) -> list[dict]:
    conn = get_connection(dsn)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """SELECT external_id, source, title, url, channel, category, thumbnail,
                          analysis, analysis_summary, posted_at, work_key
                   FROM release_items WHERE status = 'posted'
                   ORDER BY posted_at DESC, id DESC LIMIT %s""",
                (limit * OVERFETCH,),
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    items = []
    seen_works: set[str] = set()
    for row in rows:
        analysis = row["analysis"] if isinstance(row["analysis"], dict) else {}
        kind = link_kind(row["url"], row["source"])
        content_type = video_content_type(kind, row["title"], analysis)
        if content_type == "clip" or (kind == "video" and not_new_work(row, seen_works)):
            continue
        posted = row["posted_at"]
        items.append(
            {
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
                "posted_at": posted_at_utc(posted),
            }
        )
    return items[:limit]


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


def create_server(dsn: str, host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            path = urlsplit(self.path).path
            if path == "/api/releases":
                try:
                    body = json.dumps({"items": list_releases(dsn)}, ensure_ascii=False).encode()
                    self.send_response(200)
                except Exception:
                    logger.exception("Failed to load releases")
                    body = b'{"error":"Nao foi possivel carregar os lancamentos."}'
                    self.send_response(503)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
            elif path in FILES:
                filename, mime = FILES[path]
                body = (STATIC / filename).read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", f"{mime}; charset=utf-8")
                self.send_header("Cache-Control", "public, max-age=300")
            else:
                self.send_error(404)
                return
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; img-src 'self' https: data:; "
                "script-src 'self'; style-src 'self'; connect-src 'self'; "
                "base-uri 'none'; frame-ancestors 'none'",
            )
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return ThreadingHTTPServer((host, port), Handler)


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
