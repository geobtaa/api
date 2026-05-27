from __future__ import annotations

from datetime import datetime

from app.services.bridge_sync.report import (
    _split_recipients,
    build_bridge_sync_report_html,
    build_bridge_sync_report_text,
    send_bridge_sync_report_email,
)


def _sample_run(processed: int = 1726) -> dict:
    return {
        "bridge_id": 23,
        "bridge_status": "success",
        "bridge_trigger": "nightly_cron",
        "bridge_started_at": datetime(2026, 4, 24, 2, 0, 2),
        "bridge_completed_at": datetime(2026, 4, 24, 2, 4, 12),
        "bridge_stats_json": {
            "scope": "delta",
            "stage": "complete",
            "changed_since": "2026-04-23T00:00:00Z",
            "processed": processed,
            "imported": processed,
            "skipped": 0,
            "errors": 0,
            "pages_processed": 4,
            "missing": 0,
            "retired": 0,
            "changed_resources": processed,
            "search_index_refresh": {
                "enabled": True,
                "indexed": processed,
                "errors": 0,
            },
            "cache_refresh": {
                "enabled": True,
                "invalidated": 12,
                "warmed": 7,
                "errors": 0,
            },
        },
    }


def test_split_recipients_accepts_commas_semicolons_and_newlines():
    assert _split_recipients("a@example.edu; b@example.edu\nc@example.edu") == [
        "a@example.edu",
        "b@example.edu",
        "c@example.edu",
    ]


def test_build_bridge_sync_report_html_uses_brand_and_cache_sections(monkeypatch):
    monkeypatch.setenv("BRIDGE_SYNC_REPORT_MIN_DELTA_PROCESSED", "10")

    html = build_bridge_sync_report_html(_sample_run(), recent_runs=[_sample_run()])

    assert "Nightly Bridge Sync Report" in html
    assert "#003C5B" in html
    assert "Post-Sync Publishing" in html
    assert "1,726" in html
    assert "No warning conditions tripped" in html


def test_build_bridge_sync_report_flags_low_delta(monkeypatch):
    monkeypatch.setenv("BRIDGE_SYNC_REPORT_MIN_DELTA_PROCESSED", "10")

    text = build_bridge_sync_report_text(_sample_run(processed=2), recent_runs=[])

    assert "Delta processed only 2 resources" in text


def test_build_bridge_sync_report_flags_partial_elasticsearch_refresh():
    run = _sample_run(processed=8945)
    run["bridge_stats_json"]["search_index_refresh"] = {
        "enabled": True,
        "resource_ids": 5000,
        "indexed": 5000,
        "errors": 0,
    }

    text = build_bridge_sync_report_text(run, recent_runs=[])

    assert "Elasticsearch refresh received only 5,000 of 8,945 changed resource IDs." in text


def test_build_bridge_sync_report_flags_cache_refresh_error():
    run = _sample_run()
    run["bridge_stats_json"]["cache_refresh"] = {
        "enabled": True,
        "error": "No __appsignal__.py file found",
    }

    text = build_bridge_sync_report_text(run, recent_runs=[])

    assert "Cache refresh failed: No __appsignal__.py file found." in text


def test_send_bridge_sync_report_email_skips_when_disabled(monkeypatch):
    monkeypatch.delenv("BRIDGE_SYNC_REPORT_ENABLED", raising=False)

    result = send_bridge_sync_report_email(_sample_run())

    assert result == {"enabled": False, "sent": False, "reason": "disabled"}


def test_send_bridge_sync_report_email_skips_non_prd_by_default(monkeypatch):
    monkeypatch.setenv("BRIDGE_SYNC_REPORT_ENABLED", "true")
    monkeypatch.setenv("KAMAL_DEST", "dev1")

    result = send_bridge_sync_report_email(_sample_run())

    assert result == {
        "enabled": True,
        "sent": False,
        "reason": "destination_not_enabled",
        "destination": "dev1",
    }


def test_send_bridge_sync_report_email_skips_without_smtp(monkeypatch):
    monkeypatch.setenv("BRIDGE_SYNC_REPORT_ENABLED", "true")
    monkeypatch.setenv("KAMAL_DEST", "prd")
    monkeypatch.delenv("BRIDGE_SYNC_REPORT_RECIPIENTS", raising=False)
    monkeypatch.delenv("SMTP_HOST", raising=False)

    result = send_bridge_sync_report_email(_sample_run())

    assert result == {"enabled": True, "sent": False, "reason": "no_smtp_host"}


def test_send_bridge_sync_report_email_supports_sendmail(monkeypatch):
    calls = []

    def fake_run(cmd, *, input, check, timeout):
        calls.append(
            {
                "cmd": cmd,
                "input": input,
                "check": check,
                "timeout": timeout,
            }
        )

    monkeypatch.setenv("BRIDGE_SYNC_REPORT_ENABLED", "true")
    monkeypatch.setenv("KAMAL_DEST", "prd")
    monkeypatch.setenv("BRIDGE_SYNC_REPORT_DELIVERY", "sendmail")
    monkeypatch.setenv("SENDMAIL_PATH", "/usr/local/bin/sendmail")
    monkeypatch.setenv("SENDMAIL_ARGS", "-t -i")
    monkeypatch.setattr("app.services.bridge_sync.report.subprocess.run", fake_run)

    result = send_bridge_sync_report_email(_sample_run())

    assert result == {
        "enabled": True,
        "sent": True,
        "delivery": "sendmail",
        "recipients": 2,
    }
    assert calls[0]["cmd"] == ["/usr/local/bin/sendmail", "-t", "-i"]
    assert b"Nightly Bridge Sync Report" in calls[0]["input"]
    assert calls[0]["check"] is True
