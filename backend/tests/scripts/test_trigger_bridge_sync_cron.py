from __future__ import annotations

import asyncio
import json
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import scripts.trigger_bridge_sync_cron as trigger_bridge_sync_cron
from app.tasks.bridge_sync import _should_send_failure_report, _should_send_report


class _FakeAsyncResult:
    def __init__(self, task_id: str):
        self.id = task_id


class _FakeTask:
    def __init__(self):
        self.calls = []

    def apply_async(self, **kwargs):
        self.calls.append(kwargs)
        return _FakeAsyncResult("bridge-task-123")


@pytest.fixture(autouse=True)
def default_to_queued_execution(monkeypatch):
    monkeypatch.delenv("RUN_NOW", raising=False)


@pytest.mark.parametrize("run_now", ["1", "true", "yes", "on"])
def test_inline_sync_replays_checkpoint_without_queueing(monkeypatch, capsys, run_now):
    fake_task = _FakeTask()
    run_sync = AsyncMock(return_value={"bridge_id": 42, "stats": {"imported": 3}})
    monkeypatch.setattr(trigger_bridge_sync_cron, "bridge_sync_all", fake_task)
    monkeypatch.setattr(trigger_bridge_sync_cron, "_run_inline", run_sync)
    monkeypatch.setenv("RUN_NOW", run_now)
    monkeypatch.setenv("BRIDGE_TRIGGER", "nightly_cron")
    monkeypatch.delenv("CHANGED_SINCE", raising=False)
    monkeypatch.delenv("BRIDGE_LIMIT", raising=False)

    trigger_bridge_sync_cron.main()

    assert fake_task.calls == []
    run_sync.assert_awaited_once_with(
        trigger="nightly_cron", limit=None, changed_since=None, resume_from_last_success=True
    )
    assert json.loads(capsys.readouterr().out)["result"]["stats"]["imported"] == 3


@pytest.mark.asyncio
@pytest.mark.parametrize("fails", [False, True])
async def test_inline_sync_disconnects_database_on_success_and_failure(monkeypatch, fails):
    import db.database as database_module

    fake_database = SimpleNamespace(is_connected=True, disconnect=AsyncMock())
    monkeypatch.setattr(database_module, "database", fake_database)
    run_sync = AsyncMock(
        return_value={"bridge_id": 42},
        side_effect=RuntimeError("sync failed") if fails else None,
    )
    monkeypatch.setattr(trigger_bridge_sync_cron, "_bridge_sync_all_async", run_sync)
    kwargs = dict(
        trigger="incremental_cron",
        limit=250,
        changed_since="2026-10-09T00:00:00Z",
        resume_from_last_success=False,
    )
    if fails:
        with pytest.raises(RuntimeError, match="sync failed"):
            await trigger_bridge_sync_cron._run_inline(**kwargs)
    else:
        assert await trigger_bridge_sync_cron._run_inline(**kwargs) == {"bridge_id": 42}
    run_sync.assert_awaited_once_with(resource_id=None, **kwargs)
    fake_database.disconnect.assert_awaited_once()


@pytest.mark.asyncio
async def test_inline_timeout_disconnects_and_propagates_failure(monkeypatch):
    import db.database as database_module

    fake_database = SimpleNamespace(is_connected=True, disconnect=AsyncMock())
    monkeypatch.setattr(database_module, "database", fake_database)
    run_sync = AsyncMock()
    monkeypatch.setattr(trigger_bridge_sync_cron, "_bridge_sync_all_async", run_sync)
    real_wait_for = asyncio.wait_for

    async def immediate_timeout(coro, timeout):
        assert timeout == 60 * 60
        return await real_wait_for(coro, timeout=0)

    monkeypatch.setattr(trigger_bridge_sync_cron.asyncio, "wait_for", immediate_timeout)
    with pytest.raises(TimeoutError):
        await trigger_bridge_sync_cron._run_inline(trigger="incremental_cron")
    fake_database.disconnect.assert_awaited_once()


def test_main_enqueues_checkpointed_incremental_bridge_sync(monkeypatch, capsys):
    fake_task = _FakeTask()
    monkeypatch.setattr(trigger_bridge_sync_cron, "bridge_sync_all", fake_task)
    monkeypatch.delenv("BRIDGE_TRIGGER", raising=False)
    monkeypatch.delenv("BRIDGE_LIMIT", raising=False)
    monkeypatch.delenv("CHANGED_SINCE", raising=False)

    trigger_bridge_sync_cron.main()

    assert fake_task.calls == [
        {
            "kwargs": {
                "trigger": "incremental_cron",
                "limit": None,
                "changed_since": None,
                "resume_from_last_success": True,
            },
            "ignore_result": True,
        }
    ]

    payload = json.loads(capsys.readouterr().out)
    assert payload == {
        "queued": "kithe_bridge",
        "task_id": "bridge-task-123",
        "bridge_trigger": "incremental_cron",
        "limit": None,
        "changed_since": None,
        "resume_from_last_success": True,
    }


def test_main_preserves_explicit_changed_since(monkeypatch, capsys):
    fake_task = _FakeTask()
    monkeypatch.setattr(trigger_bridge_sync_cron, "bridge_sync_all", fake_task)
    monkeypatch.delenv("BRIDGE_TRIGGER", raising=False)
    monkeypatch.setenv("CHANGED_SINCE", "2026-08-17T10:00:00Z")
    monkeypatch.setenv("BRIDGE_LIMIT", "250")

    trigger_bridge_sync_cron.main()

    assert fake_task.calls[0]["kwargs"] == {
        "trigger": "incremental_cron",
        "limit": 250,
        "changed_since": "2026-08-17T10:00:00Z",
        "resume_from_last_success": False,
    }
    assert json.loads(capsys.readouterr().out)["resume_from_last_success"] is False


def test_daily_report_run_still_uses_incremental_checkpoint(monkeypatch):
    fake_task = _FakeTask()
    monkeypatch.setattr(trigger_bridge_sync_cron, "bridge_sync_all", fake_task)
    monkeypatch.setenv("BRIDGE_TRIGGER", "nightly_cron")
    monkeypatch.delenv("BRIDGE_LIMIT", raising=False)
    monkeypatch.delenv("CHANGED_SINCE", raising=False)

    trigger_bridge_sync_cron.main()

    assert fake_task.calls == [
        {
            "kwargs": {
                "trigger": "nightly_cron",
                "limit": None,
                "changed_since": None,
                "resume_from_last_success": True,
            },
            "ignore_result": True,
        }
    ]


@pytest.mark.parametrize("report_policy", [_should_send_report, _should_send_failure_report])
def test_schedule_polls_every_hour_but_reports_once_daily(monkeypatch, report_policy):
    monkeypatch.delenv("BRIDGE_SYNC_REPORT_ON_TRIGGERS", raising=False)
    monkeypatch.delenv("BRIDGE_SYNC_FAILURE_REPORT_ON_TRIGGERS", raising=False)
    crontab = Path(__file__).resolve().parents[3] / "config" / "crontab"
    scheduled_hours = Counter()
    reporting_hours = []
    for line in crontab.read_text().splitlines():
        if line.startswith("#") or "trigger_bridge_sync_cron.py" not in line:
            continue
        minute, hours, day, month, weekday, command = line.split(maxsplit=5)
        assert (minute, day, month, weekday) == ("7", "*", "*", "*")
        trigger = command.split()[0].removeprefix("BRIDGE_TRIGGER=")
        assert "RUN_NOW=1" in command.split()
        for part in hours.split(","):
            start, _, end = part.partition("-")
            for hour in range(int(start), int(end or start) + 1):
                scheduled_hours[hour] += 1
                if report_policy(trigger):
                    reporting_hours.append(hour)

    assert scheduled_hours == Counter(range(24))
    assert len(reporting_hours) == 1
    assert reporting_hours[0] not in {1, 2}  # Avoid repeated/missing DST hours.
