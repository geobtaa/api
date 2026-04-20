from datetime import datetime, timezone

import scripts.bridge_status_summary as bridge_status_summary


def test_render_payload_current_last_includes_progress_and_eta():
    payload = {
        "runs": [
            {
                "bridge_id": 17,
                "bridge_status": "running",
                "bridge_trigger": "manual",
                "bridge_started_at": "2026-04-20T15:31:34Z",
                "bridge_completed_at": None,
                "bridge_error": None,
                "bridge_stats_json": {
                    "stage": "import",
                    "processed": 2400,
                    "imported": 2399,
                    "skipped": 1,
                    "errors": 0,
                    "pages_processed": 5,
                    "last_page_size": 500,
                    "estimated_total": 84000,
                    "estimated_total_source": "last_successful_full_run",
                },
            },
            {
                "bridge_id": 16,
                "bridge_status": "success",
                "bridge_trigger": "manual",
                "bridge_started_at": "2026-03-17T22:21:34Z",
                "bridge_completed_at": "2026-03-17T23:01:51Z",
                "bridge_error": None,
                "bridge_stats_json": {
                    "stage": "complete",
                    "processed": 84291,
                    "imported": 84291,
                    "skipped": 0,
                    "errors": 0,
                    "pages_processed": 85,
                    "missing": 12,
                    "retired": 12,
                },
            },
        ]
    }

    rendered = bridge_status_summary.render_payload(
        payload,
        current_last=True,
        now=datetime(2026, 4, 20, 15, 36, 34, tzinfo=timezone.utc),
    )

    assert "current:" in rendered
    assert "processed=2400" in rendered
    assert "pages=5" in rendered
    assert "rate=8.0/s" in rendered
    assert "est_total~=84000" in rendered
    assert "progress~=2.9%" in rendered
    assert "eta~=2h50m00s" in rendered
    assert "last:" in rendered
    assert "missing=12 retired=12" in rendered


def test_render_payload_current_only_omits_last_run():
    payload = {
        "runs": [
            {
                "bridge_id": 17,
                "bridge_status": "running",
                "bridge_trigger": "manual",
                "bridge_started_at": "2026-04-20T15:31:34Z",
                "bridge_completed_at": None,
                "bridge_error": None,
                "bridge_stats_json": {
                    "stage": "import",
                    "processed": 66000,
                    "imported": 66000,
                    "skipped": 0,
                    "errors": 0,
                    "pages_processed": 132,
                    "last_page_size": 500,
                    "estimated_total": 115732,
                    "estimated_total_source": "last_successful_full_run",
                },
            },
            {
                "bridge_id": 16,
                "bridge_status": "success",
                "bridge_trigger": "manual",
                "bridge_started_at": "2026-03-17T22:21:34Z",
                "bridge_completed_at": "2026-03-17T23:01:51Z",
                "bridge_error": None,
                "bridge_stats_json": {
                    "stage": "complete",
                    "processed": 115732,
                    "imported": 115732,
                    "skipped": 0,
                    "errors": 0,
                },
            },
        ]
    }

    rendered = bridge_status_summary.render_payload(payload, current_only=True)

    assert "current:" in rendered
    assert "processed=66000" in rendered
    assert "last:" not in rendered


def test_render_payload_uses_last_successful_full_run_when_estimate_missing():
    payload = {
        "runs": [
            {
                "bridge_id": 18,
                "bridge_status": "running",
                "bridge_trigger": "manual",
                "bridge_started_at": "2026-04-20T15:31:34Z",
                "bridge_completed_at": None,
                "bridge_error": None,
                "bridge_stats_json": {
                    "stage": "import",
                    "processed": 5000,
                    "imported": 5000,
                    "skipped": 0,
                    "errors": 0,
                    "pages_processed": 10,
                },
            },
            {
                "bridge_id": 17,
                "bridge_status": "success",
                "bridge_trigger": "manual",
                "bridge_started_at": "2026-03-17T22:21:34Z",
                "bridge_completed_at": "2026-03-17T23:01:51Z",
                "bridge_error": None,
                "bridge_stats_json": {
                    "stage": "complete",
                    "processed": 83000,
                    "imported": 83000,
                    "skipped": 0,
                    "errors": 0,
                    "pages_processed": 83,
                },
            },
        ]
    }

    rendered = bridge_status_summary.render_payload(
        payload,
        current_last=True,
        now=datetime(2026, 4, 20, 15, 41, 34, tzinfo=timezone.utc),
    )

    assert "est_total~=83000" in rendered
    assert "estimate_source=last_successful_full_run" in rendered


def test_render_payload_single_run_uses_requested_resource_scope():
    payload = {
        "run": {
            "bridge_id": 19,
            "bridge_status": "success",
            "bridge_trigger": "manual",
            "bridge_started_at": "2026-04-20T15:31:34Z",
            "bridge_completed_at": "2026-04-20T15:31:40Z",
            "bridge_error": None,
            "bridge_stats_json": {
                "stage": "complete",
                "resource_id": "b1g_PJxxfKgpqpUT",
                "processed": 1,
                "imported": 1,
                "skipped": 0,
                "errors": 0,
                "pages_processed": 1,
                "estimated_total": 1,
                "estimated_total_source": "requested_resource",
            },
        }
    }

    rendered = bridge_status_summary.render_payload(payload)

    assert "scope=single:b1g_PJxxfKgpqpUT" in rendered
    assert "duration=6s" in rendered
    assert "estimate_source=requested_resource" in rendered
