from __future__ import annotations

from app.tasks.bridge_sync import _should_send_report


def test_bridge_sync_report_trigger_defaults_to_cron(monkeypatch):
    monkeypatch.delenv("BRIDGE_SYNC_REPORT_ON_TRIGGERS", raising=False)

    assert _should_send_report("nightly_cron") is True
    assert _should_send_report("cron") is True
    assert _should_send_report("manual") is False


def test_bridge_sync_report_trigger_can_include_manual(monkeypatch):
    monkeypatch.setenv("BRIDGE_SYNC_REPORT_ON_TRIGGERS", "manual,nightly_cron")

    assert _should_send_report("manual") is True


def test_bridge_sync_report_trigger_wildcard(monkeypatch):
    monkeypatch.setenv("BRIDGE_SYNC_REPORT_ON_TRIGGERS", "*")

    assert _should_send_report("anything") is True
