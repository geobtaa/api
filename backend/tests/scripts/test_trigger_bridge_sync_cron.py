from __future__ import annotations

import json
from datetime import datetime, timezone

import scripts.trigger_bridge_sync_cron as trigger_bridge_sync_cron


class _FakeAsyncResult:
    def __init__(self, task_id: str):
        self.id = task_id


class _FakeTask:
    def __init__(self):
        self.calls = []

    def apply_async(self, **kwargs):
        self.calls.append(kwargs)
        return _FakeAsyncResult("bridge-task-123")


def test_previous_utc_day_start_iso_z_uses_bridge_local_timezone(monkeypatch):
    monkeypatch.setenv("BRIDGE_SYNC_LOCAL_TIMEZONE", "America/Chicago")

    now = datetime(2026, 4, 25, 7, 0, 0, tzinfo=timezone.utc)

    assert trigger_bridge_sync_cron._previous_utc_day_start_iso_z(now) == "2026-04-24T05:00:00Z"


def test_previous_utc_day_start_iso_z_falls_back_to_chicago_timezone(monkeypatch):
    monkeypatch.setenv("BRIDGE_SYNC_LOCAL_TIMEZONE", "Not/A_Timezone")

    now = datetime(2026, 4, 25, 7, 0, 0, tzinfo=timezone.utc)

    assert trigger_bridge_sync_cron._previous_utc_day_start_iso_z(now) == "2026-04-24T05:00:00Z"


def test_main_enqueues_fire_and_forget_nightly_bridge_sync(monkeypatch, capsys):
    fake_task = _FakeTask()
    monkeypatch.setattr(trigger_bridge_sync_cron, "bridge_sync_all", fake_task)
    monkeypatch.setattr(
        trigger_bridge_sync_cron,
        "_previous_utc_day_start_iso_z",
        lambda now=None: "2026-04-24T05:00:00Z",
    )
    monkeypatch.delenv("BRIDGE_TRIGGER", raising=False)
    monkeypatch.delenv("BRIDGE_LIMIT", raising=False)
    monkeypatch.delenv("CHANGED_SINCE", raising=False)

    trigger_bridge_sync_cron.main()

    assert fake_task.calls == [
        {
            "kwargs": {
                "trigger": "nightly_cron",
                "limit": None,
                "changed_since": "2026-04-24T05:00:00Z",
            },
            "ignore_result": True,
        }
    ]

    payload = json.loads(capsys.readouterr().out)
    assert payload == {
        "queued": "kithe_bridge",
        "task_id": "bridge-task-123",
        "bridge_trigger": "nightly_cron",
        "limit": None,
        "changed_since": "2026-04-24T05:00:00Z",
    }
