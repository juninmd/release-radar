from __future__ import annotations

import contextlib
import hashlib
import hmac
import json
import logging
import math
from datetime import UTC, date, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from psycopg2.extras import RealDictCursor

from .config import Settings, get_settings
from .db import get_connection
from .dedupe import row_work_key
from .jobs import RunJob
from .links import link_kind
from .release_policy import release_state
from .settings_store import (
    coerce,
    effective_settings,
    public_settings,
    read_overrides,
    write_overrides,
)
from .web_support import Database, RateLimiter, TTLCache
from .work_identity import classify_video_title

STATIC = Path(__file__).with_name("static")
FILES = {
    "/": ("index.html", "text/html"),
    "/app.css": ("app.css", "text/css"),
    "/app.js": ("app.js", "text/javascript"),
}
MAX_BODY_BYTES = 64 * 1024
LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1", "[::1]"}
ROUTES: dict[str, set[str]] = {
    "/api/health": {"GET"},
    "/healthz": {"GET"},
    "/api/releases": {"GET"},
    "/api/run": {"GET", "POST"},
    "/api/settings": {"GET", "PUT"},
}
logger = logging.getLogger(__name__)
# Ocultar clipes e repetidos exige ler alem de `limit`; le em lotes ate completar a lista.
BATCH_SIZE = 240
MAX_SCANNED_ROWS = 5000
TRAILER_TYPES = {"trailer", "teaser", "announcement"}


class ApiError(Exception):
    """Erro de aplicacao com status HTTP; a mensagem e segura para o cliente."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


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
    allow_anonymous_writes: bool = False,
    *,
    cache_ttl: float = 15.0,
    rate_burst: int = 60,
    rate_per_second: float = 2.0,
    socket_timeout: float = 15.0,
    write_rate_burst: int = 10,
    write_rate_per_second: float = 10 / 60.0,
) -> ThreadingHTTPServer:
    base_settings = settings or get_settings()
    job = RunJob()
    db = Database(dsn)
    cache: TTLCache[list[dict]] = TTLCache(ttl=cache_ttl)
    limiter = RateLimiter(burst=rate_burst, per_second=rate_per_second)
    write_limiter = RateLimiter(burst=write_rate_burst, per_second=write_rate_per_second)

    class Handler(BaseHTTPRequestHandler):
        server_version = "ReleaseRadar"
        timeout = socket_timeout

        def do_GET(self) -> None:
            self._dispatch("GET")

        def do_POST(self) -> None:
            self._dispatch("POST")

        def do_PUT(self) -> None:
            self._dispatch("PUT")

        def do_DELETE(self) -> None:
            self._dispatch("DELETE")

        def do_PATCH(self) -> None:
            self._dispatch("PATCH")

        def do_HEAD(self) -> None:
            self._dispatch("HEAD")

        def do_OPTIONS(self) -> None:
            self._dispatch("OPTIONS")

        def _dispatch(self, method: str) -> None:
            path = urlsplit(self.path).path
            self.extra_headers: dict[str, str] = {}
            try:
                if method in {"POST", "PUT"}:
                    wait = write_limiter.acquire(self.client_address[0])
                    if wait:
                        self.extra_headers["Retry-After"] = str(max(1, math.ceil(wait)))
                        raise ApiError(429, "Muitas requisicoes. Tente novamente em instantes.")

                if path in ROUTES:
                    if method not in ROUTES[path]:
                        self._json(405, {"error": "Metodo nao permitido para esta rota."})
                    elif path == "/api/health":
                        self._json(200, {"status": "ok", "service": "release-radar"})
                    elif path == "/healthz":
                        self._ready()
                    elif path == "/api/releases":
                        self._json(200, {"items": self._releases()})
                    elif path == "/api/run":
                        self._require_token()
                        self._start_run() if method == "POST" else self._json(200, job.snapshot())
                    else:
                        self._require_token()
                        self._update_settings() if method == "PUT" else self._json(
                            200, public_settings(base_settings, load_overrides(dsn))
                        )
                elif method == "GET" and path in FILES:
                    self._send_file(path)
                else:
                    self._error(404)
            except ApiError as err:
                self._json(err.status, {"error": err.message})
            except (json.JSONDecodeError, UnicodeDecodeError):
                self._json(400, {"error": "Corpo JSON invalido."})
            except ValueError as err:
                self._json(400, {"error": str(err) or "Corpo invalido."})
            except TimeoutError:
                self.close_connection = True
                with contextlib.suppress(Exception):
                    self._json(408, {"error": "Tempo limite excedido."})
            except Exception:
                logger.exception("Failed to handle %s %s", method, path)
                self._json(500, {"error": "Falha inesperada."})

        def _releases(self) -> list[dict]:
            wait = limiter.acquire(self.client_address[0])
            if wait:
                self.extra_headers["Retry-After"] = str(max(1, math.ceil(wait)))
                raise ApiError(429, "Muitas requisicoes. Tente novamente em instantes.")
            try:
                return cache.get_or_load("releases", lambda: list_releases(db))
            except Exception:
                logger.exception("Failed to load releases")
                raise ApiError(503, "Nao foi possivel carregar os lancamentos.") from None

        def _ready(self) -> None:
            try:
                db.ping()
            except Exception:
                logger.exception("Health check failed")
                raise ApiError(503, "Banco indisponivel.") from None
            self._json(200, {"status": "ok"})

        def _require_token(self) -> None:
            if token:
                scheme, _, value = self.headers.get("Authorization", "").partition(" ")
                if scheme.lower() != "bearer" or not hmac.compare_digest(
                    value.strip().encode(), token.encode()
                ):
                    raise ApiError(401, "Nao autorizado.")
                return
            if allow_anonymous_writes:
                return
            raise ApiError(
                403,
                "Escrita desabilitada: defina RELEASE_RADAR_API_TOKEN para expor o painel.",
            )

        def _require_json_content_type(self) -> None:
            """Exigir JSON derruba o POST "simples" que uma pagina hostil dispararia.

            Vale mesmo sem corpo: um POST vazio (form/no-cors) nao tem preflight.
            """
            if not self.headers.get("Content-Type", "").lower().startswith("application/json"):
                raise ApiError(415, "Envie Content-Type: application/json.")

        def _read_json(self, optional: bool = False) -> dict[str, Any]:
            if "chunked" in self.headers.get("Transfer-Encoding", "").lower():
                raise ApiError(411, "Transfer-Encoding chunked nao suportado.")
            raw_length = self.headers.get("Content-Length")
            if raw_length is None:
                if optional:
                    return {}
                raise ApiError(400, "Corpo JSON ausente.")
            try:
                length = int(raw_length)
            except ValueError as err:
                raise ApiError(400, "Content-Length invalido.") from err
            if length < 0:
                raise ApiError(400, "Content-Length invalido.")
            if length == 0:
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
            self._require_json_content_type()
            body = self._read_json(optional=True)
            raw_dry_run = body.get("dry_run", False)
            if not isinstance(raw_dry_run, bool):
                raise ApiError(400, "dry_run deve ser verdadeiro ou falso.")
            dry_run = raw_dry_run
            raw_limit = body.get("limit")
            limit: int | None = None
            if raw_limit is not None:
                try:
                    limit = coerce("max_items_per_run", raw_limit)
                except ValueError as error:
                    raise ApiError(400, f"limit invalido: {error}") from error
            run_settings = effective_settings(base_settings, load_overrides(dsn))
            if not job.start(run_settings, dry_run=dry_run, limit=limit, dsn=dsn):
                payload = {"accepted": False, **job.snapshot()}
                self._json(409, payload)
                return
            self._json(202, {"accepted": True, **job.snapshot()})

        def _update_settings(self) -> None:
            self._require_json_content_type()
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
            etag = f'"{hashlib.sha256(body).hexdigest()[:16]}"'
            not_modified = etag in (self.headers.get("If-None-Match") or "").split(", ")
            self.send_response(304 if not_modified else 200)
            self.send_header("Content-Type", f"{mime}; charset=utf-8")
            # Revalida a cada uso: um deploy novo aparece na hora; sem mudanca, vem 304.
            self.send_header("Cache-Control", "no-cache")
            self.send_header("ETag", etag)
            self._finish_headers(
                b"" if not_modified else body, csp=True, send_body=not not_modified
            )

        def _error(self, status: int) -> None:
            self.send_error(status)

        def _json(self, status: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self._finish_headers(body, csp=True)

        def _finish_headers(self, body: bytes, *, csp: bool, send_body: bool = True) -> None:
            for name, value in self.extra_headers.items():
                self.send_header(name, value)
            self.send_header("X-Content-Type-Options", "nosniff")
            if csp:
                self.send_header(
                    "Content-Security-Policy",
                    "default-src 'self'; img-src 'self' https: data:; "
                    "script-src 'self'; style-src 'self'; connect-src 'self'; "
                    "base-uri 'none'; frame-ancestors 'none'",
                )
            if send_body:
                self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if send_body:
                self.wfile.write(body)

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            logger.info("%s - %s", self.address_string(), format % args)

    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True
    original_close = server.server_close

    def close() -> None:
        original_close()
        db.close()

    server.server_close = close  # type: ignore[method-assign]
    return server


def serve(dsn: str, host: str = "127.0.0.1", port: int = 8765) -> None:
    settings = get_settings()
    token = settings.release_radar_api_token.strip()
    local = host.strip().lower() in LOCAL_HOSTS
    allow_anonymous = local or settings.release_radar_allow_anon
    server = create_server(dsn, host, port, settings, token, allow_anonymous_writes=allow_anonymous)
    print(f"Painel do Release Radar: http://{host}:{server.server_port}")
    print("Use Ctrl+C para encerrar. O painel mostra os links publicados pelo bot.")
    if not token and not local and not allow_anonymous:
        logger.warning(
            "RELEASE_RADAR_API_TOKEN vazio em %s: /api/run e /api/settings respondem 403. "
            "Defina o token ou RELEASE_RADAR_ALLOW_ANON=true para liberar.",
            host,
        )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
