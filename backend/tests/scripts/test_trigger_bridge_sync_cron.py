from __future__ import annotations

import json

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
