import asyncio
import json
from argparse import Namespace
from unittest.mock import AsyncMock, patch

import pytest

import scripts.prime_thumbnail_cache as prime
from app.services.thumbnail_capture import CaptureResult


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["generated", "cached", "deferred"])
async def test_prime_delegates_to_shared_capture(status):
    resource = {"id": "map"}
    with (
        patch.object(prime, "fetch_distribution_context", AsyncMock()),
        patch.object(prime, "_get_thumbnail_asset_url", AsyncMock(return_value=None)),
        patch.object(prime, "ImageService") as cls,
        patch.object(
            prime,
            "capture_thumbnail",
            return_value=CaptureResult(status, "a" * 64 if status != "deferred" else None),
        ) as capture,
        patch.object(prime, "safe_record_thumbnail_state", AsyncMock()) as state,
    ):
        cls.return_value.resolve_thumbnail_source_url.return_value = "source"
        result = await prime._prime_thumbnail_for_resource(resource, force=False)
    assert result[0] == status
    assert capture.call_args.args == ("source", "map")
    assert capture.call_args.kwargs["force"] is False
    if status == "deferred":
        state.assert_not_called()
    else:
        assert state.await_args.args[0].source_hash == "a" * 64


@pytest.mark.asyncio
async def test_prime_persistence_failure_is_reported():
    with (
        patch.object(prime, "fetch_distribution_context", AsyncMock()),
        patch.object(prime, "_get_thumbnail_asset_url", AsyncMock(return_value=None)),
        patch.object(prime, "ImageService") as cls,
        patch.object(prime, "capture_thumbnail", side_effect=RuntimeError("commit failed")),
        patch.object(prime, "safe_record_thumbnail_state", AsyncMock()) as state,
    ):
        cls.return_value.resolve_thumbnail_source_url.return_value = "source"
        result = await prime._prime_thumbnail_for_resource({"id": "map"}, force=False)
    assert result == ("failed", "map", "commit failed")
    assert state.await_args.args[0].state == "failure"


def args(path, **kw):
    values = dict(
        resource_ids=["a", "b"],
        limit=None,
        report_file=str(path),
        resume_report=None,
        batch_size=1,
        concurrency=1,
        force=False,
    )
    values.update(kw)
    return Namespace(**values)


@pytest.mark.asyncio
async def test_deferred_run_is_incomplete_and_records_every_id(tmp_path):
    path = tmp_path / "run.jsonl"
    with (
        patch.object(prime, "durable_visual_asset_enabled", return_value=True),
        patch.object(prime, "_count_resources", AsyncMock(return_value=2)),
        patch.object(
            prime, "_fetch_resources_by_ids", AsyncMock(return_value=[{"id": "a"}, {"id": "b"}])
        ),
        patch.object(
            prime,
            "_prime_thumbnail_for_resource",
            AsyncMock(side_effect=[("generated", "a", "done"), ("deferred", "b", "cooldown")]),
        ),
    ):
        assert await prime._run(args(path)) == 1
    records = [json.loads(line) for line in path.read_text().splitlines()]
    assert {r["resource_id"] for r in records if r["event"] == "result"} == {"a", "b"}
    assert records[-1]["complete"] is False


@pytest.mark.asyncio
async def test_resume_rechecks_entire_scope_without_forcing_downloads(tmp_path):
    path = tmp_path / "run.jsonl"
    journal = prime.RunJournal(str(path))
    journal.write(event="scope", resource_ids=["a", "b"], limit=None)
    journal.write(event="result", resource_id="a", status="generated")
    journal.close()
    # Simulate interruption before b was ever fetched or queued.
    with (
        patch.object(prime, "durable_visual_asset_enabled", return_value=True),
        patch.object(prime, "_count_resources", AsyncMock(return_value=2)),
        patch.object(
            prime, "_fetch_resources_by_ids", AsyncMock(return_value=[{"id": "a"}, {"id": "b"}])
        ) as fetch,
        patch.object(
            prime,
            "_prime_thumbnail_for_resource",
            AsyncMock(side_effect=[("cached", "a", "verified"), ("generated", "b", "done")]),
        ) as prime_one,
    ):
        assert await prime._run(args(path, resource_ids=[], resume_report=str(path))) == 0
    fetch.assert_awaited_once_with(["a", "b"])
    assert all(call.kwargs["force"] is False for call in prime_one.await_args_list)


def test_resume_tolerates_truncated_last_record(tmp_path):
    path = tmp_path / "run.jsonl"
    path.write_text('{"event":"scope","resource_ids":[],"limit":10}\n{"event":')
    assert prime.resume_scope(str(path))["limit"] == 10


@pytest.mark.asyncio
async def test_bulk_requires_durable_storage(tmp_path):
    with patch.object(prime, "durable_visual_asset_enabled", return_value=False):
        with pytest.raises(ValueError, match="requires durable"):
            await prime._run(args(tmp_path / "run.jsonl"))


@pytest.mark.asyncio
async def test_interruption_keeps_resumable_scope_and_completed_results(tmp_path):
    path = tmp_path / "interrupted.jsonl"

    async def interrupted(resource, **kwargs):
        if resource["id"] == "b":
            await asyncio.sleep(0.01)
            raise asyncio.CancelledError()
        return "generated", "a", "committed"

    with (
        patch.object(prime, "durable_visual_asset_enabled", return_value=True),
        patch.object(prime, "_count_resources", AsyncMock(return_value=2)),
        patch.object(
            prime, "_fetch_resources_by_ids", AsyncMock(return_value=[{"id": "a"}, {"id": "b"}])
        ),
        patch.object(prime, "_prime_thumbnail_for_resource", side_effect=interrupted),
    ):
        with pytest.raises(asyncio.CancelledError):
            await prime._run(args(path))
    records = [json.loads(line) for line in path.read_text().splitlines()]
    assert prime.resume_scope(str(path))["resource_ids"] == ["a", "b"]
    assert any(r.get("status") == "generated" and r.get("resource_id") == "a" for r in records)
    assert not any(r.get("event") == "summary" for r in records)
