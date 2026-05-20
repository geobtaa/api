from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Sequence

from app.services.bridge_sync.client import KitheBridgeClient
from app.services.bridge_sync.importer import BridgeResourceImporter
from app.services.bridge_sync.repository import BridgeSyncRepository
from db.database import database

logger = logging.getLogger(__name__)

DEFAULT_BATCH_SIZE = 500
MAX_BATCH_SIZE = 1000
VALID_RESOURCE_SCOPES = {"all", "published", "bridge_active"}

BatchEnqueuer = Callable[..., Optional[str]]


def normalize_batch_size(batch_size: Optional[int]) -> int:
    if batch_size is None:
        return DEFAULT_BATCH_SIZE
    return max(1, min(int(batch_size), MAX_BATCH_SIZE))


def normalize_resource_scope(resource_scope: Optional[str]) -> str:
    scope = (resource_scope or "all").strip().lower()
    if scope not in VALID_RESOURCE_SCOPES:
        raise ValueError("resource_scope must be one of: all, published, bridge_active")
    return scope


def _chunks(items: Sequence[str], batch_size: int) -> List[List[str]]:
    return [list(items[i : i + batch_size]) for i in range(0, len(items), batch_size)]


def _coerce_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        text = value.strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            return datetime.fromisoformat(text).replace(tzinfo=None)
        except ValueError:
            pass
    return datetime.utcnow()


def _add_error_sample(
    stats: Dict[str, Any],
    *,
    stage: str,
    resource_id: Optional[str],
    error: Exception,
) -> None:
    stats["errors"] = int(stats.get("errors") or 0) + 1
    signature = f"{error.__class__.__name__}: {str(error)[:180]}"
    signature_counts = stats.setdefault("_error_signature_counts", {})
    signature_counts[signature] = int(signature_counts.get(signature) or 0) + 1

    samples = stats.setdefault("error_samples", [])
    if len(samples) < 20:
        samples.append(
            {
                "stage": stage,
                "resource_id": resource_id,
                "error": str(error)[:500],
            }
        )


def _finalize_error_stats(stats: Dict[str, Any]) -> None:
    signature_counts = stats.pop("_error_signature_counts", {})
    for item in stats.get("error_signatures") or []:
        signature = item.get("signature") if isinstance(item, dict) else None
        if signature:
            signature_counts[str(signature)] = signature_counts.get(str(signature), 0) + int(
                item.get("count") or 0
            )
    if signature_counts:
        stats["error_signatures"] = [
            {"signature": signature, "count": count}
            for signature, count in sorted(
                signature_counts.items(), key=lambda kv: kv[1], reverse=True
            )[:10]
        ]


async def queue_batched_bridge_sync(
    *,
    trigger: str = "manual_batched",
    batch_size: Optional[int] = None,
    resource_scope: str = "all",
    max_resources: Optional[int] = None,
    enqueue_batch: BatchEnqueuer,
    repo: Optional[BridgeSyncRepository] = None,
) -> Dict[str, Any]:
    if not database.is_connected:
        await database.connect()

    repo = repo or BridgeSyncRepository()
    scope = normalize_resource_scope(resource_scope)
    normalized_batch_size = normalize_batch_size(batch_size)
    resource_limit = int(max_resources) if max_resources is not None else None
    if resource_limit is not None and resource_limit < 0:
        raise ValueError("max_resources must be greater than or equal to 0")

    run_id = await repo.create_sync_run(bridge_trigger=trigger)
    await repo.cancel_other_running_runs(
        keep_bridge_id=run_id,
        reason=f"superseded by batched bridge sync run {run_id}",
    )

    base_stats: Dict[str, Any] = {
        "scope": "batched_full",
        "resource_scope": scope,
        "stage": "snapshotting",
        "batch_size": normalized_batch_size,
        "processed": 0,
        "imported": 0,
        "skipped": 0,
        "errors": 0,
        "missing": 0,
        "retired": 0,
        "updated_at": datetime.utcnow().isoformat() + "Z",
        "post_sync": "run a full Elasticsearch reindex after this batched sync completes",
    }
    if resource_limit is not None:
        base_stats["max_resources"] = resource_limit

    await repo.update_sync_run(bridge_id=run_id, bridge_stats_json=base_stats)

    resource_ids = await repo.list_resource_ids_for_batched_sync(
        resource_scope=scope,
        limit=resource_limit,
    )
    batches = _chunks(resource_ids, normalized_batch_size)
    total_batches = len(batches)
    queued_task_ids: List[str] = []

    stats = {
        **base_stats,
        "stage": "batching",
        "estimated_total": len(resource_ids),
        "estimated_total_source": f"{scope}_resource_snapshot",
        "total_resources": len(resource_ids),
        "total_batches": total_batches,
        "batches_queued": total_batches,
        "batches_completed": 0,
        "batches_failed": 0,
        "batches_finished": 0,
        "updated_at": datetime.utcnow().isoformat() + "Z",
    }
    await repo.update_sync_run(bridge_id=run_id, bridge_stats_json=stats)

    if not batches:
        stats["stage"] = "complete"
        await repo.finalize_sync_run(
            bridge_id=run_id,
            bridge_status="success",
            bridge_stats_json=stats,
        )
        return {"bridge_id": run_id, "stats": stats, "queued_batches": 0}

    try:
        for index, resource_id_batch in enumerate(batches, start=1):
            task_id = enqueue_batch(
                bridge_id=run_id,
                resource_ids=resource_id_batch,
                batch_number=index,
                total_batches=total_batches,
                trigger=trigger,
            )
            if task_id:
                queued_task_ids.append(str(task_id))
    except Exception as exc:
        failed_stats = {
            **stats,
            "stage": "failed",
            "batches_queued": len(queued_task_ids),
            "errors": int(stats.get("errors") or 0) + 1,
            "error_samples": [
                {
                    "stage": "enqueue_batches",
                    "resource_id": None,
                    "error": str(exc)[:500],
                }
            ],
            "updated_at": datetime.utcnow().isoformat() + "Z",
        }
        await repo.finalize_sync_run(
            bridge_id=run_id,
            bridge_status="failed",
            bridge_stats_json=failed_stats,
            bridge_error=str(exc),
        )
        raise

    return {
        "bridge_id": run_id,
        "stats": {**stats, "queued_task_ids_sample": queued_task_ids[:20]},
        "queued_batches": total_batches,
    }


async def sync_bridge_resource_batch(
    *,
    bridge_id: int,
    resource_ids: Sequence[str],
    batch_number: Optional[int] = None,
    total_batches: Optional[int] = None,
    task_id: Optional[str] = None,
    client: Optional[KitheBridgeClient] = None,
    importer: Optional[BridgeResourceImporter] = None,
    repo: Optional[BridgeSyncRepository] = None,
) -> Dict[str, Any]:
    if not database.is_connected:
        await database.connect()

    repo = repo or BridgeSyncRepository()
    run = await repo.get_sync_run(bridge_id)
    if not run:
        raise ValueError(f"Bridge sync run {bridge_id} was not found")
    if str(run.get("bridge_status") or "").lower() != "running":
        return {
            "bridge_id": bridge_id,
            "batch_number": batch_number,
            "skipped": True,
            "reason": f"run status is {run.get('bridge_status')}",
        }

    run_started_at = _coerce_datetime(run.get("bridge_started_at"))
    client = client or KitheBridgeClient()
    importer = importer or BridgeResourceImporter(repo=repo)

    batch_stats: Dict[str, Any] = {
        "processed": len(resource_ids),
        "imported": 0,
        "skipped": 0,
        "errors": 0,
        "missing": 0,
        "retired": 0,
        "total_batches": total_batches,
    }
    records: List[Dict[str, Any]] = []
    missing_ids: List[str] = []

    for resource_id in resource_ids:
        rid = str(resource_id or "").strip()
        if not rid:
            batch_stats["skipped"] += 1
            continue
        try:
            record = await asyncio.to_thread(client.fetch_record, rid)
        except Exception as exc:
            logger.warning("Bridge batched fetch failed for %s: %s", rid, exc)
            _add_error_sample(
                batch_stats,
                stage="fetch_record",
                resource_id=rid,
                error=exc,
            )
            continue

        if record is None:
            missing_ids.append(rid)
        else:
            records.append(record)

    if records:
        import_stats = await importer.upsert_records(
            records,
            run_started_at=run_started_at,
            batch_size=min(len(records), normalize_batch_size(None)),
        )
        for key in ("imported", "skipped", "errors"):
            batch_stats[key] = int(batch_stats.get(key) or 0) + int(import_stats.get(key) or 0)
        if import_stats.get("error_samples"):
            batch_stats.setdefault("error_samples", []).extend(import_stats["error_samples"])
        if import_stats.get("error_signatures"):
            batch_stats.setdefault("error_signatures", []).extend(import_stats["error_signatures"])

    if missing_ids:
        missing_since = datetime.utcnow()
        await repo.mark_resources_missing(missing_ids, missing_since=missing_since)
        retired_count = await repo.retire_missing_resources(
            missing_ids,
            retired_at=missing_since,
        )
        batch_stats["missing"] = len(missing_ids)
        batch_stats["retired"] = retired_count

    _finalize_error_stats(batch_stats)
    parent_stats = await repo.record_batched_batch_result(
        bridge_id=bridge_id,
        batch_stats=batch_stats,
        batch_number=batch_number,
        task_id=task_id,
        failed=False,
    )
    return {
        "bridge_id": bridge_id,
        "batch_number": batch_number,
        "stats": batch_stats,
        "parent_stats": parent_stats,
    }
