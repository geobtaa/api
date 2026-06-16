from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.services.bridge_sync.cache_refresh import refresh_cache_for_changed_resources
from app.services.bridge_sync.changed_resources import resource_ids_for_bridge_records
from app.services.bridge_sync.client import KitheBridgeClient
from app.services.bridge_sync.importer import BridgeResourceImporter
from app.services.bridge_sync.repository import BridgeSyncRepository
from app.services.bridge_sync.search_index import index_changed_resources
from db.database import database

logger = logging.getLogger(__name__)


def _merge_stats(total: Dict[str, Any], page_stats: Dict[str, Any]) -> None:
    for key in ("processed", "imported", "skipped", "errors"):
        total[key] = int(total.get(key, 0)) + int(page_stats.get(key, 0) or 0)

    samples = list(total.get("error_samples") or [])
    samples.extend(page_stats.get("error_samples") or [])
    if samples:
        total["error_samples"] = samples[:20]

    signatures: Dict[str, int] = {
        item.get("signature"): int(item.get("count") or 0)
        for item in (total.get("error_signatures") or [])
        if item.get("signature")
    }
    for item in page_stats.get("error_signatures") or []:
        signature = item.get("signature")
        if not signature:
            continue
        signatures[signature] = signatures.get(signature, 0) + int(item.get("count") or 0)
    if signatures:
        total["error_signatures"] = [
            {"signature": key, "count": value}
            for key, value in sorted(signatures.items(), key=lambda kv: kv[1], reverse=True)[:10]
        ]


async def sync_bridge(
    *,
    trigger: str = "manual",
    limit: Optional[int] = None,
    changed_since: Optional[str] = None,
    resource_id: Optional[str] = None,
    client: Optional[KitheBridgeClient] = None,
    importer: Optional[BridgeResourceImporter] = None,
    repo: Optional[BridgeSyncRepository] = None,
) -> Dict[str, Any]:
    """Page the bridge API, UPSERT resources, and retire records that disappear."""

    if not database.is_connected:
        await database.connect()

    repo = repo or BridgeSyncRepository()
    client = client or KitheBridgeClient()
    importer = importer or BridgeResourceImporter(repo=repo)
    resource_id_norm = (resource_id or "").strip() or None

    changed_since_norm: Optional[str] = None
    if changed_since:
        # Normalize to UTC ISO-8601 with `Z` suffix, since the bridge expects that format.
        try:
            if changed_since.endswith("Z"):
                dt = datetime.fromisoformat(changed_since[:-1] + "+00:00")
            else:
                dt = datetime.fromisoformat(changed_since)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            dt = dt.astimezone(timezone.utc)
            changed_since_norm = dt.isoformat().replace("+00:00", "Z")
        except Exception as exc:
            raise ValueError(
                f"changed_since must be an ISO-8601 datetime, got {changed_since!r}"
            ) from exc

    run_id = await repo.create_sync_run(bridge_trigger=trigger)
    run_started_at = datetime.utcnow()
    await repo.cancel_other_running_runs(
        keep_bridge_id=run_id, reason=f"superseded by bridge sync run {run_id}"
    )

    cursor: Optional[str] = None
    last_cursor: Optional[str] = None
    pages_processed = 0
    stats: Dict[str, Any] = {"processed": 0, "imported": 0, "skipped": 0, "errors": 0}
    search_refresh_resource_ids: list[str] = []
    cache_refresh_resource_ids: list[str] = []
    if resource_id_norm:
        stats["scope"] = "single"
        stats["estimated_total"] = 1
        stats["estimated_total_source"] = "requested_resource"
    elif changed_since_norm:
        stats["scope"] = "delta"
    else:
        stats["scope"] = "full"
    if changed_since_norm:
        stats["changed_since"] = changed_since_norm
    if resource_id_norm:
        stats["resource_id"] = resource_id_norm

    try:
        if not changed_since_norm and not resource_id_norm:
            estimated_total, estimated_total_source = await repo.estimate_full_sync_total()
            if estimated_total and estimated_total > 0:
                stats["estimated_total"] = estimated_total
                stats["estimated_total_source"] = estimated_total_source

        await repo.update_sync_run(
            bridge_id=run_id,
            bridge_stats_json={
                "stage": "starting",
                "updated_at": datetime.utcnow().isoformat() + "Z",
                **stats,
            },
        )

        found_resource = False
        if resource_id_norm:
            record = await asyncio.to_thread(client.fetch_record, resource_id_norm)
            pages_processed = 1
            found_resource = bool(record)
            page_records = [record] if record else []
            search_refresh_resource_ids.extend(resource_ids_for_bridge_records(page_records))
            cache_refresh_resource_ids.extend(
                resource_ids_for_bridge_records(page_records, include_related=True)
            )
            page_stats = await importer.upsert_records(
                page_records,
                run_started_at=run_started_at,
                batch_size=1,
            )
            _merge_stats(stats, page_stats)

            await repo.update_sync_run(
                bridge_id=run_id,
                bridge_stats_json={
                    "stage": "import",
                    "updated_at": datetime.utcnow().isoformat() + "Z",
                    "pages_processed": pages_processed,
                    "last_page_size": len(page_records),
                    "matched_page_size": len(page_records),
                    "has_more": False,
                    **stats,
                },
                bridge_last_cursor=last_cursor,
            )
        else:
            while True:
                page = await asyncio.to_thread(
                    client.fetch_page,
                    cursor=cursor,
                    limit=limit,
                    changed_since=changed_since_norm,
                )
                pages_processed += 1

                page_records = page.data
                search_refresh_resource_ids.extend(resource_ids_for_bridge_records(page_records))
                if changed_since_norm:
                    cache_refresh_resource_ids.extend(
                        resource_ids_for_bridge_records(page_records, include_related=True)
                    )
                page_stats = await importer.upsert_records(
                    page_records,
                    run_started_at=run_started_at,
                    batch_size=max(1, min(int(limit or getattr(client, "page_size", 500)), 500)),
                )
                _merge_stats(stats, page_stats)
                last_cursor = page.next_cursor

                await repo.update_sync_run(
                    bridge_id=run_id,
                    bridge_stats_json={
                        "stage": "import",
                        "updated_at": datetime.utcnow().isoformat() + "Z",
                        "pages_processed": pages_processed,
                        "last_page_size": len(page.data),
                        "matched_page_size": len(page_records),
                        "has_more": page.has_more,
                        **stats,
                    },
                    bridge_last_cursor=last_cursor,
                )

                if not page.has_more:
                    break
                if not page.next_cursor:
                    raise RuntimeError("Bridge crawl did not receive next_cursor for the next page")
                cursor = page.next_cursor

        missing_ids = []
        retired_count = 0
        # Delta crawl (`changed_since`) does not have a complete snapshot, so we
        # must not retire "missing" resources that simply weren't returned.
        if resource_id_norm:
            if not found_resource:
                raise RuntimeError(f"Bridge resource {resource_id_norm} was not found")
        elif not changed_since_norm:
            missing_ids = await repo.mark_missing_stale(run_started_at=run_started_at)
            retired_count = await repo.retire_missing_resources(
                missing_ids, retired_at=datetime.utcnow()
            )
            search_refresh_resource_ids.extend(missing_ids)
            cache_refresh_resource_ids.extend(missing_ids)
        stats.update(
            {
                "stage": "complete",
                "pages_processed": pages_processed,
                "missing": len(missing_ids),
                "retired": retired_count,
                "updated_at": datetime.utcnow().isoformat() + "Z",
            }
        )
        if resource_id_norm:
            stats["found"] = found_resource

        if search_refresh_resource_ids:
            stats["changed_resources"] = len({rid for rid in search_refresh_resource_ids if rid})
            try:
                stats["search_index_refresh"] = await index_changed_resources(
                    search_refresh_resource_ids
                )
            except Exception as index_exc:
                logger.warning("Bridge search index refresh failed; continuing. err=%s", index_exc)
                stats["search_index_refresh"] = {"enabled": True, "error": str(index_exc)}

        if cache_refresh_resource_ids:
            try:
                stats["cache_refresh"] = await refresh_cache_for_changed_resources(
                    cache_refresh_resource_ids
                )
            except Exception as cache_exc:
                logger.warning("Bridge cache refresh failed; continuing. err=%s", cache_exc)
                stats["cache_refresh"] = {"enabled": True, "error": str(cache_exc)}

        await repo.finalize_sync_run(
            bridge_id=run_id,
            bridge_status="success",
            bridge_stats_json=stats,
            bridge_last_cursor=last_cursor,
        )
        logger.info(
            "Bridge sync completed run_id=%s pages=%s imported=%s retired=%s",
            run_id,
            pages_processed,
            stats.get("imported"),
            stats.get("retired"),
        )
        return {"bridge_id": run_id, "stats": stats, "bridge_last_cursor": last_cursor}
    except Exception as exc:
        logger.error("Bridge sync failed: %s", exc, exc_info=True)
        try:
            await repo.update_sync_run(
                bridge_id=run_id,
                bridge_stats_json={
                    **stats,
                    "stage": "failed",
                    "pages_processed": pages_processed,
                    "updated_at": datetime.utcnow().isoformat() + "Z",
                },
                bridge_last_cursor=last_cursor,
                bridge_error=str(exc),
            )
        except Exception:
            pass
        await repo.finalize_sync_run(
            bridge_id=run_id,
            bridge_status="failed",
            bridge_last_cursor=last_cursor,
            bridge_error=str(exc),
        )
        try:
            exc.bridge_sync_run_id = run_id
        except Exception:
            pass
        raise
