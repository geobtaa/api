from __future__ import annotations

import asyncio
import copy
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import app.services.bridge_sync.incremental as incremental
from app.services.bridge_sync.client import BridgePage

CUTOFF = "2026-09-29T21:51:55Z"
WATERMARK = "2026-09-29T21:56:55Z"


class MemoryRepository:
    def __init__(self):
        self.runs = []

    async def create_sync_run_if_idle(self, bridge_trigger):
        run_id = len(self.runs) + 1
        self.runs.append({"bridge_id": run_id, "bridge_status": "running"})
        return run_id, None

    async def latest_page_checkpoint(self, *, changed_since, before_run_id):
        for run in reversed(self.runs):
            if run["bridge_id"] < before_run_id:
                stats = run.get("bridge_stats_json", {})
                if stats.get("changed_since") == changed_since:
                    return copy.deepcopy(run) if run["bridge_status"] != "success" else None
        return None

    async def update_sync_run(self, *, bridge_id, **values):
        self.runs[bridge_id - 1].update(copy.deepcopy(values))

    finalize_sync_run = update_sync_run


class PageClient:
    def __init__(self):
        self.calls = []

    def fetch_page(self, *, cursor, limit, changed_since):
        self.calls.append((cursor, limit, changed_since))
        record = {
            "id": "second" if cursor else "first",
            "kithe_updated_at": "2026-10-11T12:00:00Z" if cursor else "2026-10-12T12:00:00Z",
        }
        return BridgePage(
            data=[record], next_cursor=None if cursor else "page-two", has_more=not cursor
        )


@pytest.fixture
def pipeline(monkeypatch):
    index = AsyncMock(return_value={"indexed": 1, "errors": 0})
    refresh = AsyncMock(return_value={"warmed": 1, "errors": 0})
    monkeypatch.setattr(incremental, "index_changed_resources", index)
    monkeypatch.setattr(incremental, "refresh_cache_for_changed_resources", refresh)
    return SimpleNamespace(
        repo=MemoryRepository(),
        client=PageClient(),
        importer=SimpleNamespace(
            upsert_records=AsyncMock(return_value={"processed": 1, "imported": 1, "errors": 0})
        ),
        index=index,
        refresh=refresh,
    )


async def run(pipeline, **kwargs):
    return await incremental.sync_incremental_bridge(
        trigger="incremental_cron",
        changed_since=CUTOFF,
        source_high_watermark=WATERMARK,
        repo=pipeline.repo,
        client=pipeline.client,
        importer=pipeline.importer,
        **kwargs,
    )


@pytest.mark.asyncio
async def test_paused_crawl_resumes_published_page_before_publishing_watermark(pipeline):
    first = await run(pipeline, budget_seconds=0)
    assert first["paused"] is True
    assert pipeline.repo.runs[0]["bridge_status"] == "paused"
    checkpoint = first["stats"]["page_checkpoint"]
    assert checkpoint["cursor"] == "page-two"
    assert checkpoint["stats"]["processed"] == 1
    pipeline.index.assert_awaited_once_with(["first"])
    pipeline.refresh.assert_awaited_once_with(["first"])

    second = await run(pipeline)
    assert pipeline.client.calls == [(None, 100, CUTOFF), ("page-two", 100, CUTOFF)]
    assert pipeline.repo.runs[-1]["bridge_status"] == "success"
    assert second["stats"]["processed"] == 2
    assert second["stats"]["source_high_watermark"] == "2026-10-12T12:00:00Z"
    assert "page_checkpoint" not in second["stats"]


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["importer", "index", "refresh"])
async def test_failed_second_page_retries_only_unpublished_page(pipeline, stage):
    await run(pipeline, budget_seconds=0)
    operation = (
        pipeline.importer.upsert_records if stage == "importer" else getattr(pipeline, stage)
    )
    operation.side_effect = RuntimeError("temporary outage")
    with pytest.raises(RuntimeError, match="temporary outage"):
        await run(pipeline)
    failed = pipeline.repo.runs[-1]
    assert failed["bridge_status"] == "failed"
    assert failed["bridge_stats_json"]["page_checkpoint"]["cursor"] == "page-two"
    assert failed["bridge_stats_json"]["page_checkpoint"]["stats"]["processed"] == 1
    operation.side_effect = None
    result = await run(pipeline)
    assert result["stats"]["processed"] == 2
    assert [call[0] for call in pipeline.client.calls] == [None, "page-two", "page-two"]


@pytest.mark.asyncio
async def test_refresh_error_result_cannot_checkpoint_page(pipeline):
    pipeline.refresh.return_value = {"errors": 1}
    with pytest.raises(incremental.BridgeSyncIncompleteError, match="cache refresh"):
        await run(pipeline)
    checkpoint = pipeline.repo.runs[-1]["bridge_stats_json"]["page_checkpoint"]
    assert checkpoint["cursor"] is None
    assert checkpoint["stats"]["source_high_watermark"] == WATERMARK
    assert checkpoint["stats"]["processed"] == 0


@pytest.mark.asyncio
async def test_timeout_during_refresh_preserves_completed_page(pipeline):
    await run(pipeline, budget_seconds=0)
    pipeline.refresh.side_effect = asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):
        await run(pipeline)
    failed = pipeline.repo.runs[-1]
    assert failed["bridge_error"] == "CancelledError"
    assert failed["bridge_stats_json"]["page_checkpoint"]["cursor"] == "page-two"
    assert failed["bridge_status"] == "failed"


@pytest.mark.asyncio
async def test_active_run_is_not_resumed_concurrently(pipeline):
    pipeline.repo.create_sync_run_if_idle = AsyncMock(return_value=(None, 42))
    result = await run(pipeline)
    assert result["skipped"] is True
    assert pipeline.client.calls == []


@pytest.mark.asyncio
async def test_failed_success_finalization_retains_last_durable_cursor(pipeline):
    await run(pipeline, budget_seconds=0)
    finalize = pipeline.repo.finalize_sync_run

    async def fail_success(**kwargs):
        if kwargs["bridge_status"] == "success":
            raise RuntimeError("lost database connection")
        await finalize(**kwargs)

    pipeline.repo.finalize_sync_run = fail_success
    with pytest.raises(RuntimeError, match="lost database"):
        await run(pipeline)
    assert pipeline.repo.runs[-1]["bridge_stats_json"]["page_checkpoint"]["cursor"] == "page-two"
