import asyncio
import logging
import os
from typing import Any, Coroutine, Dict, Optional

from app.services.bridge_sync.harvest import sync_bridge
from app.services.bridge_sync.report import send_bridge_sync_report_for_run
from app.tasks.worker import celery_app
from db.database import database

logger = logging.getLogger(__name__)

_loop: Optional[asyncio.AbstractEventLoop] = None


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
) -> Dict[str, Any]:
    return _run(
        _bridge_sync_all_async(
            trigger=trigger,
            limit=limit,
            changed_since=changed_since,
            resource_id=resource_id,
        )
    )


async def _bridge_sync_all_async(
    trigger: str,
    limit: Optional[int],
    changed_since: Optional[str],
    resource_id: Optional[str],
) -> Dict[str, Any]:
    if not database.is_connected:
        await database.connect()
    logger.info(
        "Bridge sync starting: trigger=%s limit=%s changed_since=%s resource_id=%s",
        trigger,
        limit,
        changed_since,
        resource_id,
    )
    try:
        result = await sync_bridge(
            trigger=trigger,
            limit=limit,
            changed_since=changed_since,
            resource_id=resource_id,
        )
    except Exception as exc:
        run_id = getattr(exc, "bridge_sync_run_id", None)
        if run_id and _should_send_report(trigger):
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
    if run_id and _should_send_report(trigger):
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
