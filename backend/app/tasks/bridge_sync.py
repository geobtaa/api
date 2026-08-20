import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Coroutine, Dict, Optional

from app.services.bridge_sync.batched import (
    queue_batched_bridge_sync,
    sync_bridge_resource_batch,
)
from app.services.bridge_sync.harvest import sync_bridge
from app.services.bridge_sync.report import send_bridge_sync_report_for_run
from app.services.bridge_sync.repository import BridgeSyncRepository
from app.tasks.worker import celery_app
from db.database import database

logger = logging.getLogger(__name__)

_loop: Optional[asyncio.AbstractEventLoop] = None
DEFAULT_BRIDGE_SYNC_CHECKPOINT_OVERLAP_SECONDS = 300
DEFAULT_BRIDGE_SYNC_INITIAL_LOOKBACK_HOURS = 24


def _get_loop() -> asyncio.AbstractEventLoop:
    global _loop
    if _loop is None or _loop.is_closed():
        _loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_loop)
    return _loop


def _run(coro: Coroutine[Any, Any, Any]) -> Any:
    return _get_loop().run_until_complete(coro)


def _report_triggers() -> set[str]:
    raw = os.getenv("BRIDGE_SYNC_REPORT_ON_TRIGGERS", "nightly_cron,cron")
    return {part.strip().lower() for part in raw.split(",") if part.strip()}


def _should_send_report(trigger: str) -> bool:
    trigger_norm = (trigger or "").strip().lower()
    return trigger_norm in _report_triggers() or "*" in _report_triggers()


def _failure_report_triggers() -> set[str]:
    raw = os.getenv(
        "BRIDGE_SYNC_FAILURE_REPORT_ON_TRIGGERS",
        "nightly_cron,cron,incremental_cron",
    )
    return {part.strip().lower() for part in raw.split(",") if part.strip()}


def _should_send_failure_report(trigger: str) -> bool:
    trigger_norm = (trigger or "").strip().lower()
    triggers = _failure_report_triggers()
    return trigger_norm in triggers or "*" in triggers


def _nonnegative_env_int(name: str, default: int) -> int:
    raw = os.getenv(name, str(default))
    try:
        return max(0, int(raw))
    except ValueError:
        return default


def _utc_iso_z(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


async def _incremental_checkpoint(
    repo: BridgeSyncRepository,
    *,
    now: Optional[datetime] = None,
) -> tuple[str, str]:
    source_high_watermark = await repo.latest_successful_crawl_source_watermark()
    if source_high_watermark is None:
        fallback_hours = _nonnegative_env_int(
            "BRIDGE_SYNC_INITIAL_LOOKBACK_HOURS",
            DEFAULT_BRIDGE_SYNC_INITIAL_LOOKBACK_HOURS,
        )
        source_high_watermark = (now or datetime.now(timezone.utc)) - timedelta(
            hours=fallback_hours
        )

    overlap_seconds = _nonnegative_env_int(
        "BRIDGE_SYNC_CHECKPOINT_OVERLAP_SECONDS",
        DEFAULT_BRIDGE_SYNC_CHECKPOINT_OVERLAP_SECONDS,
    )
    changed_since = source_high_watermark - timedelta(seconds=overlap_seconds)
    return _utc_iso_z(changed_since), _utc_iso_z(source_high_watermark)


@celery_app.task(
    bind=True,
    name="bridge_sync_all",
    soft_time_limit=60 * 60,
    time_limit=70 * 60,
)
def bridge_sync_all(
    self,
    trigger: str = "manual",
    limit: Optional[int] = None,
    changed_since: Optional[str] = None,
    resource_id: Optional[str] = None,
    resume_from_last_success: bool = False,
) -> Dict[str, Any]:
    return _run(
        _bridge_sync_all_async(
            trigger=trigger,
            limit=limit,
            changed_since=changed_since,
            resource_id=resource_id,
            resume_from_last_success=resume_from_last_success,
        )
    )


async def _bridge_sync_all_async(
    trigger: str,
    limit: Optional[int],
    changed_since: Optional[str],
    resource_id: Optional[str],
    resume_from_last_success: bool = False,
) -> Dict[str, Any]:
    if not database.is_connected:
        await database.connect()
    repo: Optional[BridgeSyncRepository] = None
    source_high_watermark: Optional[str] = None
    if resume_from_last_success and not changed_since and not resource_id:
        repo = BridgeSyncRepository()
        changed_since, source_high_watermark = await _incremental_checkpoint(repo)
    logger.info(
        "Bridge sync starting: trigger=%s limit=%s changed_since=%s resource_id=%s "
        "resume_from_last_success=%s",
        trigger,
        limit,
        changed_since,
        resource_id,
        resume_from_last_success,
    )
    try:
        result = await sync_bridge(
            trigger=trigger,
            limit=limit,
            changed_since=changed_since,
            resource_id=resource_id,
            source_high_watermark=source_high_watermark,
            repo=repo,
        )
    except Exception as exc:
        run_id = getattr(exc, "bridge_sync_run_id", None)
        if run_id and _should_send_failure_report(trigger):
            try:
                await send_bridge_sync_report_for_run(int(run_id))
            except Exception as report_exc:
                logger.warning(
                    "Bridge sync report failed for failed run_id=%s: %s",
                    run_id,
                    report_exc,
                    exc_info=True,
                )
        raise

    run_id = result.get("bridge_id")
    if run_id and not result.get("skipped") and _should_send_report(trigger):
        try:
            report_stats = await send_bridge_sync_report_for_run(int(run_id))
            result["report"] = report_stats
        except Exception as exc:
            logger.warning(
                "Bridge sync report failed for run_id=%s: %s",
                run_id,
                exc,
                exc_info=True,
            )
            result["report"] = {"enabled": True, "sent": False, "error": str(exc)}
    return result


@celery_app.task(
    bind=True,
    name="bridge_sync_enqueue_batches",
    soft_time_limit=10 * 60,
    time_limit=15 * 60,
)
def bridge_sync_enqueue_batches(
    self,
    trigger: str = "manual_batched",
    batch_size: Optional[int] = None,
    resource_scope: str = "all",
    max_resources: Optional[int] = None,
) -> Dict[str, Any]:
    return _run(
        _bridge_sync_enqueue_batches_async(
            trigger=trigger,
            batch_size=batch_size,
            resource_scope=resource_scope,
            max_resources=max_resources,
        )
    )


async def _bridge_sync_enqueue_batches_async(
    trigger: str,
    batch_size: Optional[int],
    resource_scope: str,
    max_resources: Optional[int],
) -> Dict[str, Any]:
    if not database.is_connected:
        await database.connect()

    def _enqueue_batch(**kwargs: Any) -> Optional[str]:
        task = bridge_sync_resource_batch.apply_async(kwargs=kwargs, ignore_result=True)
        return str(task.id) if task.id else None

    return await queue_batched_bridge_sync(
        trigger=trigger,
        batch_size=batch_size,
        resource_scope=resource_scope,
        max_resources=max_resources,
        enqueue_batch=_enqueue_batch,
    )


@celery_app.task(
    bind=True,
    name="bridge_sync_resource_batch",
    soft_time_limit=30 * 60,
    time_limit=35 * 60,
)
def bridge_sync_resource_batch(
    self,
    bridge_id: int,
    resource_ids: list[str],
    batch_number: Optional[int] = None,
    total_batches: Optional[int] = None,
    trigger: str = "manual_batched",
) -> Dict[str, Any]:
    try:
        return _run(
            sync_bridge_resource_batch(
                bridge_id=bridge_id,
                resource_ids=resource_ids,
                batch_number=batch_number,
                total_batches=total_batches,
                task_id=getattr(self.request, "id", None),
            )
        )
    except Exception as exc:
        logger.error(
            "Bridge sync batch failed: bridge_id=%s batch_number=%s trigger=%s err=%s",
            bridge_id,
            batch_number,
            trigger,
            exc,
            exc_info=True,
        )
        _run(
            _record_failed_bridge_sync_batch(
                bridge_id=bridge_id,
                batch_number=batch_number,
                total_batches=total_batches,
                task_id=getattr(self.request, "id", None),
                exc=exc,
            )
        )
        raise


async def _record_failed_bridge_sync_batch(
    *,
    bridge_id: int,
    batch_number: Optional[int],
    total_batches: Optional[int],
    task_id: Optional[str],
    exc: Exception,
) -> None:
    if not database.is_connected:
        await database.connect()
    from app.services.bridge_sync.repository import BridgeSyncRepository

    repo = BridgeSyncRepository()
    await repo.record_batched_batch_result(
        bridge_id=bridge_id,
        batch_number=batch_number,
        task_id=task_id,
        failed=True,
        batch_stats={
            "processed": 0,
            "imported": 0,
            "skipped": 0,
            "errors": 1,
            "missing": 0,
            "deleted": 0,
            "retired": 0,
            "total_batches": total_batches,
            "error_samples": [
                {
                    "stage": "batch_task",
                    "resource_id": None,
                    "error": str(exc)[:500],
                }
            ],
            "error_signatures": [
                {
                    "signature": f"{exc.__class__.__name__}: {str(exc)[:180]}",
                    "count": 1,
                }
            ],
        },
    )
