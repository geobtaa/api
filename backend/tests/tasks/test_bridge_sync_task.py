from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

import app.tasks.bridge_sync as bridge_sync_task
from app.services.bridge_sync.repository import BridgeSyncRepository
from app.tasks.bridge_sync import (
    _bridge_sync_all_async,
    _incremental_checkpoint,
    _should_send_failure_report,
    _should_send_report,
)


def test_bridge_sync_report_trigger_defaults_to_cron(monkeypatch):
    monkeypatch.delenv("BRIDGE_SYNC_REPORT_ON_TRIGGERS", raising=False)

    assert _should_send_report("nightly_cron") is True
    assert _should_send_report("cron") is True
    assert _should_send_report("incremental_cron") is False
    assert _should_send_report("manual") is False


def test_bridge_sync_failure_report_includes_incremental_cron(monkeypatch):
    monkeypatch.delenv("BRIDGE_SYNC_FAILURE_REPORT_ON_TRIGGERS", raising=False)

    assert _should_send_failure_report("incremental_cron") is True
    assert _should_send_failure_report("nightly_cron") is True
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
async def test_scheduled_sync_reports_failed_incremental_run(monkeypatch):
    error = RuntimeError("sync failed")
    error.bridge_sync_run_id = 42
    sync_bridge = AsyncMock(side_effect=error)
    send_report = AsyncMock(return_value={"sent": True})
    monkeypatch.setattr(bridge_sync_task, "sync_bridge", sync_bridge)
    monkeypatch.setattr(bridge_sync_task, "send_bridge_sync_report_for_run", send_report)
    monkeypatch.delenv("BRIDGE_SYNC_FAILURE_REPORT_ON_TRIGGERS", raising=False)

    with pytest.raises(RuntimeError, match="sync failed"):
        await _bridge_sync_all_async(
            trigger="incremental_cron",
            limit=500,
            changed_since="2026-08-17T15:00:00Z",
            resource_id=None,
        )

    send_report.assert_awaited_once_with(42)


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
