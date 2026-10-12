"""Incremental crawls with durable checkpoints after publishing each page."""

from __future__ import annotations

import asyncio
import copy
import logging
import time
from datetime import datetime
from typing import Any

from app.services.bridge_sync.cache_refresh import refresh_cache_for_changed_resources
from app.services.bridge_sync.changed_resources import resource_ids_for_bridge_records
from app.services.bridge_sync.client import KitheBridgeClient
from app.services.bridge_sync.harvest import (
    BridgeSyncIncompleteError,
    _advance_source_high_watermark,
    _merge_stats,
    _parse_utc_timestamp,
    _refresh_error_count,
    _utc_iso_z,
)
from app.services.bridge_sync.importer import BridgeResourceImporter
from app.services.bridge_sync.repository import BridgeSyncRepository
from app.services.bridge_sync.search_index import index_changed_resources

logger = logging.getLogger(__name__)


def _merge_refresh_stats(total: dict[str, Any], page: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(total)
    for key, value in page.items():
        if isinstance(value, dict):
            result[key] = _merge_refresh_stats(result.get(key, {}), value)
        elif isinstance(value, bool) or key == "batch_size":
            result[key] = value
        elif isinstance(value, (int, float)):
            result[key] = result.get(key, 0) + value
        else:
            result[key] = value
    return result


async def sync_incremental_bridge(
    *,
    trigger: str,
    changed_since: str,
    source_high_watermark: str,
    repo: BridgeSyncRepository,
    page_size: int = 100,
    budget_seconds: float = 50 * 60,
    client: KitheBridgeClient | None = None,
    importer: BridgeResourceImporter | None = None,
) -> dict[str, Any]:
    """Resume only pages whose import, search, and cache refresh all completed.

    A paused/failed crawl never publishes a global source watermark. The opaque
    cursor and original lower bound are retained until the entire crawl succeeds.
    Replaying an interrupted page is safe because all publishing is idempotent.
    """
    client = client or KitheBridgeClient()
    importer = importer or BridgeResourceImporter(repo=repo)
    run_id, active_run_id = await repo.create_sync_run_if_idle(bridge_trigger=trigger)
    if run_id is None:
        return {
            "bridge_id": active_run_id,
            "skipped": True,
            "stats": {"stage": "skipped", "active_bridge_id": active_run_id},
            "bridge_last_cursor": None,
        }

    stats: dict[str, Any] = {
        "scope": "delta",
        "changed_since": changed_since,
        "source_high_watermark": source_high_watermark,
        "processed": 0,
        "imported": 0,
        "skipped": 0,
        "errors": 0,
        "deleted": 0,
        "pages_processed": 0,
        "page_checkpoint_version": 1,
    }
    cursor = None
    started = time.monotonic()
    run_started_at = datetime.utcnow()

    async def save(stage: str) -> None:
        stats.update(stage=stage, updated_at=datetime.utcnow().isoformat() + "Z")
        await repo.update_sync_run(bridge_id=run_id, bridge_stats_json=copy.deepcopy(stats))

    try:
        previous = await repo.latest_page_checkpoint(
            changed_since=changed_since, before_run_id=run_id
        )
        if previous:
            checkpoint = previous["bridge_stats_json"].get("page_checkpoint")
            if checkpoint:
                stats.update(copy.deepcopy(checkpoint["stats"]))
                cursor = checkpoint["cursor"]
                stats["resumed_from_run_id"] = previous["bridge_id"]
        # Keep the last *published* page separate from in-flight page statistics.
        stats["page_checkpoint"] = {"cursor": cursor, "stats": copy.deepcopy(stats)}
        await save("starting")

        while True:
            page = await asyncio.to_thread(
                client.fetch_page,
                cursor=cursor,
                limit=page_size,
                changed_since=changed_since,
            )
            if page.has_more and (not page.next_cursor or page.next_cursor == cursor):
                raise BridgeSyncIncompleteError("Bridge page did not advance its cursor")

            await save("import")
            page_stats = await importer.upsert_records(
                page.data, run_started_at=run_started_at, batch_size=page_size
            )
            if int(page_stats.get("errors") or 0):
                stats["incomplete_page"] = page_stats
                stats["errors"] = int(page_stats["errors"])
                raise BridgeSyncIncompleteError("Bridge page import completed with errors")

            search_ids = resource_ids_for_bridge_records(page.data)
            cache_ids = resource_ids_for_bridge_records(page.data, include_related=True)
            await save("index")
            search_stats = await index_changed_resources(search_ids)
            if _refresh_error_count(search_stats):
                stats["refresh_failures"] = {
                    "search_index_refresh": _refresh_error_count(search_stats)
                }
                raise BridgeSyncIncompleteError("Bridge page search refresh completed with errors")

            await save("refreshing")
            cache_stats = await refresh_cache_for_changed_resources(cache_ids)
            if _refresh_error_count(cache_stats):
                stats["refresh_failures"] = {"cache_refresh": _refresh_error_count(cache_stats)}
                raise BridgeSyncIncompleteError("Bridge page cache refresh completed with errors")

            _merge_stats(stats, page_stats)
            stats["pages_processed"] += 1
            stats["last_page_size"] = len(page.data)
            stats["has_more"] = page.has_more
            watermark = _advance_source_high_watermark(
                _parse_utc_timestamp(stats["source_high_watermark"]), page.data
            )
            if watermark is not None:
                stats["source_high_watermark"] = _utc_iso_z(watermark)
            stats["search_index_refresh"] = _merge_refresh_stats(
                stats.get("search_index_refresh", {}), search_stats
            )
            stats["cache_refresh"] = _merge_refresh_stats(
                stats.get("cache_refresh", {}), cache_stats
            )
            logger.info(
                "Bridge incremental page published run_id=%s pages=%s imported=%s has_more=%s",
                run_id,
                stats["pages_processed"],
                stats["imported"],
                page.has_more,
            )

            if not page.has_more:
                final_stats = {
                    key: value for key, value in stats.items() if key != "page_checkpoint"
                }
                final_stats.update(stage="complete", updated_at=datetime.utcnow().isoformat() + "Z")
                await repo.finalize_sync_run(
                    bridge_id=run_id, bridge_status="success", bridge_stats_json=final_stats
                )
                return {"bridge_id": run_id, "stats": final_stats, "bridge_last_cursor": None}

            cursor = page.next_cursor
            completed = {key: value for key, value in stats.items() if key != "page_checkpoint"}
            stats["page_checkpoint"] = {"cursor": cursor, "stats": copy.deepcopy(completed)}
            await save("page_complete")
            if time.monotonic() - started >= budget_seconds:
                stats.update(stage="paused", updated_at=datetime.utcnow().isoformat() + "Z")
                await repo.finalize_sync_run(
                    bridge_id=run_id,
                    bridge_status="paused",
                    bridge_stats_json=stats,
                    bridge_last_cursor=cursor,
                )
                return {"bridge_id": run_id, "paused": True, "stats": stats}
    except (Exception, asyncio.CancelledError) as exc:
        stats.update(stage="failed", updated_at=datetime.utcnow().isoformat() + "Z")
        await repo.finalize_sync_run(
            bridge_id=run_id,
            bridge_status="failed",
            bridge_stats_json=stats,
            bridge_error=str(exc) or exc.__class__.__name__,
        )
        exc.bridge_sync_run_id = run_id
        raise
