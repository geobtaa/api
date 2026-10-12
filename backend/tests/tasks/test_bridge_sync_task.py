from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import app.services.bridge_sync.harvest as bridge_harvest
import app.tasks.bridge_sync as bridge_sync_task
from app.services.bridge_sync.client import BridgePage
from app.services.bridge_sync.repository import BridgeSyncRepository

_bridge_sync_all_async = bridge_sync_task._bridge_sync_all_async
_incremental_checkpoint = bridge_sync_task._incremental_checkpoint
_should_send_failure_report = bridge_sync_task._should_send_failure_report
_should_send_report = bridge_sync_task._should_send_report


@pytest.mark.asyncio
async def test_cancelled_crawl_is_failed_and_keeps_checkpoint_ineligible(monkeypatch):
    monkeypatch.setattr(bridge_harvest, "database", SimpleNamespace(is_connected=True))
    repo = SimpleNamespace(
        create_sync_run_if_idle=AsyncMock(return_value=(42, None)),
        update_sync_run=AsyncMock(),
        finalize_sync_run=AsyncMock(),
    )
    client = SimpleNamespace(
        page_size=500,
        fetch_page=lambda **kwargs: BridgePage(data=[], next_cursor=None, has_more=False),
    )
    importer = SimpleNamespace(upsert_records=AsyncMock(side_effect=asyncio.CancelledError()))

    with pytest.raises(asyncio.CancelledError):
        await bridge_harvest.sync_bridge(
            changed_since="2026-10-09T00:00:00Z", client=client, importer=importer, repo=repo
        )

    final = repo.finalize_sync_run.await_args.kwargs
    assert final["bridge_id"] == 42
    assert final["bridge_status"] == "failed"
    assert final["bridge_stats_json"]["stage"] == "failed"
    assert final["bridge_error"] == "CancelledError"


@pytest.fixture(autouse=True)
def connected_database(monkeypatch):
    monkeypatch.setattr(bridge_sync_task, "database", SimpleNamespace(is_connected=True))


def test_bridge_sync_report_trigger_defaults_to_cron(monkeypatch):
    monkeypatch.delenv("BRIDGE_SYNC_REPORT_ON_TRIGGERS", raising=False)

    assert _should_send_report("nightly_cron") is True
    assert _should_send_report("cron") is True
    assert _should_send_report("incremental_cron") is False
    assert _should_send_report("manual") is False


def test_bridge_sync_failure_report_defaults_to_daily_triggers(monkeypatch):
    monkeypatch.delenv("BRIDGE_SYNC_FAILURE_REPORT_ON_TRIGGERS", raising=False)

    assert _should_send_failure_report("incremental_cron") is False
    assert _should_send_failure_report("nightly_cron") is True
    assert _should_send_failure_report("cron") is True
    assert _should_send_failure_report("manual") is False


def test_bridge_sync_report_trigger_can_include_manual(monkeypatch):
    monkeypatch.setenv("BRIDGE_SYNC_REPORT_ON_TRIGGERS", "manual,nightly_cron")

    assert _should_send_report("manual") is True


def test_bridge_sync_report_trigger_wildcard(monkeypatch):
    monkeypatch.setenv("BRIDGE_SYNC_REPORT_ON_TRIGGERS", "*")

    assert _should_send_report("anything") is True


@pytest.mark.asyncio
async def test_incremental_checkpoint_replays_from_source_high_watermark(monkeypatch):
    monkeypatch.delenv("BRIDGE_SYNC_CHECKPOINT_OVERLAP_SECONDS", raising=False)
    repo = BridgeSyncRepository()
    repo.latest_successful_crawl_source_watermark = AsyncMock(
        return_value=datetime(2026, 8, 17, 15, 30, tzinfo=timezone.utc)
    )

    changed_since, source_high_watermark = await _incremental_checkpoint(repo)

    assert changed_since == "2026-08-17T15:25:00Z"
    assert source_high_watermark == "2026-08-17T15:30:00Z"


@pytest.mark.asyncio
async def test_incremental_checkpoint_uses_bootstrap_window_without_history(monkeypatch):
    monkeypatch.setenv("BRIDGE_SYNC_CHECKPOINT_OVERLAP_SECONDS", "0")
    monkeypatch.setenv("BRIDGE_SYNC_INITIAL_LOOKBACK_HOURS", "12")
    repo = BridgeSyncRepository()
    repo.latest_successful_crawl_source_watermark = AsyncMock(return_value=None)

    changed_since, source_high_watermark = await _incremental_checkpoint(
        repo,
        now=datetime(2026, 8, 17, 16, 0, tzinfo=timezone.utc),
    )

    assert changed_since == "2026-08-17T04:00:00Z"
    assert source_high_watermark == "2026-08-17T04:00:00Z"


@pytest.mark.asyncio
async def test_scheduled_sync_resolves_and_passes_checkpoint(monkeypatch):
    monkeypatch.setenv("BRIDGE_SYNC_CHECKPOINT_OVERLAP_SECONDS", "300")
    repo = BridgeSyncRepository()
    repo.latest_successful_crawl_source_watermark = AsyncMock(
        return_value=datetime(2026, 8, 17, 15, 30, tzinfo=timezone.utc)
    )
    sync_bridge = AsyncMock(return_value={"bridge_id": 42, "stats": {}})
    monkeypatch.setattr(bridge_sync_task, "BridgeSyncRepository", lambda: repo)
    monkeypatch.setattr(bridge_sync_task, "sync_bridge", sync_bridge)

    result = await _bridge_sync_all_async(
        trigger="incremental_cron",
        limit=500,
        changed_since=None,
        resource_id=None,
        resume_from_last_success=True,
    )

    assert result["bridge_id"] == 42
    sync_bridge.assert_awaited_once_with(
        trigger="incremental_cron",
        limit=500,
        changed_since="2026-08-17T15:25:00Z",
        resource_id=None,
        source_high_watermark="2026-08-17T15:30:00Z",
        repo=repo,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("trigger", "should_report"),
    [("incremental_cron", False), ("nightly_cron", True), ("manual", False)],
)
@pytest.mark.parametrize("error_type", [RuntimeError, asyncio.CancelledError])
async def test_scheduled_sync_failure_reporting(monkeypatch, trigger, should_report, error_type):
    error = error_type("sync failed")
    error.bridge_sync_run_id = 42
    sync_bridge = AsyncMock(side_effect=error)
    send_report = AsyncMock(return_value={"sent": True})
    monkeypatch.setattr(bridge_sync_task, "sync_bridge", sync_bridge)
    monkeypatch.setattr(bridge_sync_task, "send_bridge_sync_report_for_run", send_report)
    monkeypatch.delenv("BRIDGE_SYNC_FAILURE_REPORT_ON_TRIGGERS", raising=False)

    with pytest.raises(error_type, match="sync failed"):
        await _bridge_sync_all_async(
            trigger=trigger,
            limit=500,
            changed_since="2026-08-17T15:00:00Z",
            resource_id=None,
        )

    if should_report:
        send_report.assert_awaited_once_with(42)
    else:
        send_report.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("trigger", "skipped", "should_report"),
    [
        ("incremental_cron", False, False),
        ("nightly_cron", False, True),
        ("nightly_cron", True, False),
        ("manual", False, False),
    ],
)
async def test_scheduled_sync_success_reporting(monkeypatch, trigger, skipped, should_report):
    sync_bridge = AsyncMock(return_value={"bridge_id": 42, "skipped": skipped, "stats": {}})
    send_report = AsyncMock(return_value={"sent": True})
    monkeypatch.setattr(bridge_sync_task, "sync_bridge", sync_bridge)
    monkeypatch.setattr(bridge_sync_task, "send_bridge_sync_report_for_run", send_report)
    monkeypatch.delenv("BRIDGE_SYNC_REPORT_ON_TRIGGERS", raising=False)

    result = await _bridge_sync_all_async(
        trigger=trigger,
        limit=500,
        changed_since="2026-08-17T15:00:00Z",
        resource_id=None,
    )

    if should_report:
        send_report.assert_awaited_once_with(42)
        assert result["report"] == {"sent": True}
    else:
        send_report.assert_not_awaited()
        assert "report" not in result


@pytest.mark.parametrize("triggers", ["incremental_cron", " MANUAL, Incremental_Cron ", "*"])
def test_incremental_failure_reports_can_be_explicitly_enabled(monkeypatch, triggers):
    monkeypatch.setenv("BRIDGE_SYNC_FAILURE_REPORT_ON_TRIGGERS", triggers)

    assert _should_send_failure_report("incremental_cron") is True


@pytest.mark.asyncio
async def test_latest_successful_crawl_watermark_ignores_ineligible_runs(monkeypatch):
    repo = BridgeSyncRepository()
    repo.list_sync_runs = AsyncMock(
        return_value=[
            {
                "bridge_started_at": datetime(2026, 8, 17, 16, 0),
                "bridge_stats_json": {
                    "scope": "single",
                    "resource_id": "example",
                    "source_high_watermark": "2026-08-17T16:00:00Z",
                },
            },
            {
                "bridge_started_at": datetime(2026, 8, 17, 15, 0),
                "bridge_stats_json": {
                    "scope": "batched_full",
                    "source_high_watermark": "2026-08-17T15:00:00Z",
                },
            },
            {
                "bridge_started_at": datetime(2026, 8, 17, 14, 30),
                "bridge_stats_json": {"scope": "delta"},
            },
            {
                "bridge_started_at": datetime(2026, 8, 17, 14, 0),
                "bridge_stats_json": {
                    "scope": "delta",
                    "changed_since": "2026-08-17T13:00:00Z",
                    "source_high_watermark": "2026-08-17T14:20:00Z",
                },
            },
            {
                "bridge_started_at": datetime(2026, 8, 17, 13, 0),
                "bridge_stats_json": {
                    "scope": "full",
                    "source_high_watermark": "2026-08-17T14:25:00Z",
                },
            },
        ]
    )

    checkpoint = await repo.latest_successful_crawl_source_watermark()

    assert checkpoint == datetime(2026, 8, 17, 14, 25, tzinfo=timezone.utc)
    repo.list_sync_runs.assert_awaited_once_with(
        bridge_status="success",
        limit=1000,
        offset=0,
    )
