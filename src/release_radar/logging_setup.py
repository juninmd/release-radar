from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

from rich.console import Console
from rich.logging import RichHandler

# Campos extras passados via `logger.info(..., extra={...})` entram no JSON.
_STANDARD = frozenset(logging.makeLogRecord({}).__dict__) | {"message", "asctime"}


class JsonFormatter(logging.Formatter):
    """Uma linha JSON por registro, pronta para Loki/Datadog/CloudWatch."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        payload.update({k: v for k, v in record.__dict__.items() if k not in _STANDARD})
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(verbose: bool = False, json_logs: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    if json_logs:
        handler: logging.Handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
    else:
        handler = RichHandler(console=Console(stderr=True), rich_tracebacks=True)
    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=[handler],
        force=True,
    )
