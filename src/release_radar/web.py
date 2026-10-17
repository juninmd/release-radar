from __future__ import annotations

import json
import logging
import os
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from psycopg2.extras import RealDictCursor

from .config import Settings, get_settings
from .db import get_connection
from .jobs import RunJob
from .links import link_kind
from .release_policy import release_state
from .settings_store import (
    effective_settings,
    public_settings,
    read_overrides,
    write_overrides,
)

STATIC = Path(__file__).with_name("static")
FILES = {
    "/": ("index.html", "text/html"),
    "/app.css": ("app.css", "text/css"),
    "/app.js": ("app.js", "text/javascript"),
}
MAX_BODY_BYTES = 64 * 1024
logger = logging.getLogger(__name__)


class ApiError(Exception):
    """Erro de aplicacao com status HTTP; a mensagem e segura para o cliente."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


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


def load_overrides(dsn: str) -> dict[str, Any]:
    conn = get_connection(dsn)
    try:
        return read_overrides(conn)
    finally:
        conn.close()


def create_server(
    dsn: str,
    host: str = "127.0.0.1",
    port: int = 8765,
    settings: Settings | None = None,
    token: str = "",
) -> ThreadingHTTPServer:
    base_settings = settings or get_settings()
    job = RunJob()

    class Handler(BaseHTTPRequestHandler):
        server_version = "ReleaseRadar"

        def do_GET(self) -> None:
            self._dispatch("GET")

        def do_POST(self) -> None:
            self._dispatch("POST")

        def do_PUT(self) -> None:
            self._dispatch("PUT")

        def _dispatch(self, method: str) -> None:
            path = urlsplit(self.path).path
            try:
                if path == "/api/health":
                    self._json(200, {"status": "ok", "service": "release-radar"})
                elif path == "/api/releases" and method == "GET":
                    self._json(200, {"items": self._releases()})
                elif path == "/api/run" and method == "POST":
                    self._require_token()
                    self._start_run()
                elif path == "/api/run" and method == "GET":
                    self._require_token()
                    self._json(200, job.snapshot())
                elif path == "/api/settings" and method == "GET":
                    self._require_token()
                    self._json(200, public_settings(base_settings, load_overrides(dsn)))
                elif path == "/api/settings" and method == "PUT":
                    self._require_token()
                    self._update_settings()
                elif method == "GET" and path in FILES:
                    self._send_file(path)
                else:
                    self._error(404)
            except ApiError as err:
                self._json(err.status, {"error": err.message})
            except (json.JSONDecodeError, ValueError) as err:
                self._json(400, {"error": str(err) or "Corpo invalido."})
            except Exception:
                logger.exception("Failed to handle %s %s", method, path)
                self._json(500, {"error": "Falha inesperada."})

        def _releases(self) -> list[dict]:
            try:
                return list_releases(dsn)
            except Exception:
                logger.exception("Failed to load releases")
                raise ApiError(503, "Nao foi possivel carregar os lancamentos.") from None

        def _require_token(self) -> None:
            if not token:
                return
            header = self.headers.get("Authorization", "")
            expected = f"Bearer {token}"
            if header != expected:
                raise ApiError(401, "Nao autorizado.")

        def _read_json(self, optional: bool = False) -> dict[str, Any]:
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = 0
            if length <= 0:
                if optional:
                    return {}
                raise ApiError(400, "Corpo JSON ausente.")
            if length > MAX_BODY_BYTES:
                raise ApiError(413, "Corpo grande demais.")
            raw = self.rfile.read(length)
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise ApiError(400, "Envie um objeto JSON.")
            return data

        def _start_run(self) -> None:
            body = self._read_json(optional=True)
            dry_run = bool(body.get("dry_run", False))
            raw_limit = body.get("limit")
            limit: int | None = None
            if raw_limit is not None:
                try:
                    limit = int(raw_limit)
                except (TypeError, ValueError) as exc:
                    raise ApiError(400, "limit deve ser um numero inteiro") from exc
                if limit <= 0:
                    raise ApiError(400, "limit deve ser maior que zero")
            run_settings = effective_settings(base_settings, load_overrides(dsn))
            if not job.start(run_settings, dry_run=dry_run, limit=limit, dsn=dsn):
                payload = {"accepted": False, **job.snapshot()}
                self._json(409, payload)
                return
            self._json(202, {"accepted": True, **job.snapshot()})

        def _update_settings(self) -> None:
            body = self._read_json()
            conn = get_connection(dsn)
            try:
                saved = write_overrides(conn, body)
                overrides = read_overrides(conn)
            finally:
                conn.close()
            payload = public_settings(base_settings, overrides)
            payload["saved"] = sorted(saved)
            self._json(200, payload)

        def _send_file(self, path: str) -> None:
            filename, mime = FILES[path]
            body = (STATIC / filename).read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", f"{mime}; charset=utf-8")
            self.send_header("Cache-Control", "public, max-age=300")
            self._finish_headers(body, csp=True)

        def _error(self, status: int) -> None:
            self.send_error(status)

        def _json(self, status: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self._finish_headers(body, csp=True)

        def _finish_headers(self, body: bytes, *, csp: bool) -> None:
            self.send_header("X-Content-Type-Options", "nosniff")
            if csp:
                self.send_header(
                    "Content-Security-Policy",
                    "default-src 'self'; img-src 'self' https: data:; "
                    "script-src 'self'; style-src 'self'; connect-src 'self'; "
                    "base-uri 'none'; frame-ancestors 'none'",
                )
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            logger.debug("%s - %s", self.address_string(), format % args)

    return ThreadingHTTPServer((host, port), Handler)


def serve(dsn: str, host: str = "127.0.0.1", port: int = 8765) -> None:
    token = os.environ.get("RELEASE_RADAR_API_TOKEN", "").strip()
    server = create_server(dsn, host, port, get_settings(), token)
    print(f"Painel do Release Radar: http://{host}:{server.server_port}")
    print("Use Ctrl+C para encerrar. O painel mostra os links publicados pelo bot.")
    if not token and host not in {"127.0.0.1", "localhost"}:
        logger.warning(
            "RELEASE_RADAR_API_TOKEN vazio: /api/run e /api/settings ficam abertos "
            "para quem alcancar %s. Defina o token antes de expor o painel.",
            host,
        )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
