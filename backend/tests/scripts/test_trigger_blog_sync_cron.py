from __future__ import annotations

import json

import scripts.trigger_blog_sync_cron as trigger_blog_sync_cron


class _FakeAsyncResult:
    def __init__(self, task_id: str):
        self.id = task_id


class _FakeTask:
    def __init__(self):
        self.calls = []

    def apply_async(self, **kwargs):
        self.calls.append(kwargs)
        return _FakeAsyncResult("blog-task-123")


def test_main_enqueues_blog_sync_without_result_subscription(monkeypatch, capsys):
    fake_task = _FakeTask()
    monkeypatch.setattr(trigger_blog_sync_cron, "gin_blog_sync", fake_task)
    monkeypatch.delenv("RUN_NOW", raising=False)

    trigger_blog_sync_cron.main()

    assert fake_task.calls == [{"ignore_result": True}]
    payload = json.loads(capsys.readouterr().out)
    assert payload == {"queued": "gin_blog_sync", "task_id": "blog-task-123"}
