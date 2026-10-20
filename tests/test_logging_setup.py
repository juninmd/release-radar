from __future__ import annotations

import json
import logging

from release_radar.logging_setup import JsonFormatter


def test_json_formatter_emits_one_line_with_extra_fields() -> None:
    record = logging.getLogger("radar").makeRecord(
        "radar",
        logging.INFO,
        __file__,
        1,
        "Run finished",
        (),
        None,
        extra={"event": "run_summary", "posted": 2, "source_errors": {"steam": 1}},
    )

    line = JsonFormatter().format(record)

    data = json.loads(line)
    assert "\n" not in line
    assert data["message"] == "Run finished"
    assert data["level"] == "INFO"
    assert data["event"] == "run_summary"
    assert data["source_errors"] == {"steam": 1}


def test_json_formatter_includes_traceback() -> None:
    try:
        raise ValueError("falhou")
    except ValueError:
        import sys

        record = logging.getLogger("radar").makeRecord(
            "radar", logging.ERROR, __file__, 1, "erro", (), sys.exc_info()
        )

    assert "ValueError: falhou" in json.loads(JsonFormatter().format(record))["exc_info"]
