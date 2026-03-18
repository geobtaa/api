import asyncio
import logging
from typing import Any, Coroutine, Dict, Optional

from app.services.bridge_sync.harvest import sync_bridge
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


@celery_app.task(
    bind=True,
    name="bridge_sync_all",
    soft_time_limit=60 * 60,
    time_limit=70 * 60,
)
def bridge_sync_all(self, trigger: str = "manual", limit: Optional[int] = None) -> Dict[str, Any]:
    return _run(_bridge_sync_all_async(trigger=trigger, limit=limit))


async def _bridge_sync_all_async(trigger: str, limit: Optional[int]) -> Dict[str, Any]:
    if not database.is_connected:
        await database.connect()
    logger.info("Bridge sync starting: trigger=%s limit=%s", trigger, limit)
    return await sync_bridge(trigger=trigger, limit=limit)
