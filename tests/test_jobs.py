from __future__ import annotations

import threading

from release_radar import jobs as jobs_module
from release_radar.config import Settings
from release_radar.jobs import RunJob
from release_radar.pipeline import RunStats


def test_only_one_round_runs_at_a_time(monkeypatch) -> None:
    started = threading.Event()
    release = threading.Event()

    def fake_run_sync(_settings, limit=None, dry_run=False, dsn=None):  # noqa: ANN001
        started.set()
        release.wait(5)
        return RunStats(discovered=2, posted=1)

    monkeypatch.setattr(jobs_module, "run_sync", fake_run_sync)
    job = RunJob()
    settings = Settings(_env_file=None)

    assert job.start(settings, dry_run=True, limit=None) is True
    assert started.wait(5), "a rodada não começou"
    assert job.snapshot()["running"] is True
    assert job.start(settings, dry_run=True, limit=None) is False

    release.set()
    assert job.wait(5) is True
    snapshot = job.snapshot()
    assert snapshot["running"] is False
    assert snapshot["stats"]["discovered"] == 2
    assert snapshot["stats"]["posted"] == 1
    assert snapshot["error"] is None
    assert snapshot["finished_at"] is not None


def test_failure_is_reported_without_leaking_details(monkeypatch) -> None:
    def failing_run_sync(*_args, **_kwargs):  # noqa: ANN002, ANN003
        raise RuntimeError('connection to server at "db.internal" port 5432 failed')

    monkeypatch.setattr(jobs_module, "run_sync", failing_run_sync)
    job = RunJob()
    assert job.start(Settings(_env_file=None), dry_run=True, limit=None) is True
    assert job.wait(5) is True

    snapshot = job.snapshot()
    assert snapshot["running"] is False
    assert snapshot["stats"] is None
    assert "db.internal" not in snapshot["error"]
    assert "5432" not in snapshot["error"]
