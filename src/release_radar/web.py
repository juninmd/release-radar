from __future__ import annotations

import json
import logging
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from psycopg2.extras import RealDictCursor

from .db import get_connection
from .links import link_kind
from .release_policy import release_state

STATIC = Path(__file__).with_name("static")
FILES = {
    "/": ("index.html", "text/html"),
    "/app.css": ("app.css", "text/css"),
    "/app.js": ("app.js", "text/javascript"),
}
logger = logging.getLogger(__name__)


def list_releases(dsn: str, limit: int = 120) -> list[dict]:
    conn = get_connection(dsn)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """SELECT external_id, source, title, url, channel, category, thumbnail,
                          analysis, analysis_summary, posted_at
                   FROM release_items WHERE status = 'posted'
                   ORDER BY posted_at DESC, id DESC LIMIT %s""",
                (limit,),
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    items = []
    for row in rows:
        analysis = row["analysis"] if isinstance(row["analysis"], dict) else {}
        kind = link_kind(row["url"], row["source"])
        posted = row["posted_at"]
        items.append(
            {
                "id": row["external_id"],
                "source": row["source"],
                "kind": kind,
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
                "posted_at": posted.isoformat() if isinstance(posted, (datetime, date)) else None,
            }
        )
    return items


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
