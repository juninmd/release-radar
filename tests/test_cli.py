import getpass
import json
import os
import subprocess
import sys

import pytest
from psycopg2.extensions import parse_dsn

from release_radar import cli
from release_radar.pipeline import RunStats


def test_cli_reports_readable_results_and_machine_readable_json(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli, "run_sync", lambda *_args, **_kwargs: RunStats(skipped_released=2))
    monkeypatch.setattr("sys.argv", ["release-radar", "run", "--dry-run"])
    cli.main()
    text = capsys.readouterr().out
    assert "Já lançados" in text
    assert "teste a seco" in text
    monkeypatch.setattr("sys.argv", ["release-radar", "run", "--dry-run", "--json"])
    cli.main()
    payload = json.loads(capsys.readouterr().out)
    assert payload["skipped_released"] == 2
    assert payload["posted"] == 0


def test_cli_rejects_invalid_limits_before_running_bot(monkeypatch) -> None:
    monkeypatch.setattr("sys.argv", ["release-radar", "run", "--limit", "0"])
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == 2


def test_json_stdout_stays_parseable_with_real_pipeline_logs(postgres_dsn: str) -> None:
    config = parse_dsn(postgres_dsn)
    env = {
        **os.environ,
        **{
            f"POSTGRES_{field.upper()}": config.get(pg_field, default)
            for field, pg_field, default in (
                ("host", "host", "localhost"),
                ("port", "port", "5432"),
                ("db", "dbname", "postgres"),
                ("user", "user", getpass.getuser()),
                ("password", "password", ""),
            )
        },
        "PGOPTIONS": config.get("options", ""),
        "YOUTUBE_SOURCES": "",
        "RSS_SOURCES": "",
        "STEAM_ENABLED": "false",
        "KITSU_ENABLED": "false",
        "TELEGRAM_BOT_TOKEN": "",
        "TELEGRAM_CHAT_ID": "",
        "LLM_API_KEY": "",
    }
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from release_radar.cli import main; main()",
            "run",
            "--dry-run",
            "--json",
        ],
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=20,
        check=True,
    )
    assert json.loads(result.stdout)["discovered"] == 0
    assert "Discovered 0 candidates" in result.stderr
