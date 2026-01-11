import asyncio
import logging
from typing import Any, Coroutine, Dict, List, Optional

from app.services.ogm_harvest.harvest import harvest_repo
from app.services.ogm_harvest.repository import OGMHarvestRepository
from app.tasks.worker import celery_app
from db.database import database

logger = logging.getLogger(__name__)

_loop: Optional[asyncio.AbstractEventLoop] = None


def _get_loop() -> asyncio.AbstractEventLoop:
    """
    Celery tasks here are synchronous wrappers around async work.
    Avoid `asyncio.run()` per task: it creates/closes an event loop each call, which can
    break long-lived async resources (like the asyncpg pool) with 'Event loop is closed'.
    """
    global _loop
    if _loop is None or _loop.is_closed():
        _loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_loop)
    return _loop


def _run(coro: Coroutine[Any, Any, Any]) -> Any:
    return _get_loop().run_until_complete(coro)


@celery_app.task(
    bind=True,
    name="ogm_harvest_repo",
    # Harvesting can take a while (git clone/pull + parsing many records).
    soft_time_limit=60 * 60,  # 1 hour
    time_limit=70 * 60,  # 70 minutes
)
def ogm_harvest_repo(self, repo_name: str, trigger: str = "manual") -> Dict[str, Any]:
    """Harvest a single OGM repo and write local dump artifacts."""
    return _run(_ogm_harvest_repo_async(repo_name=repo_name, trigger=trigger))


async def _ogm_harvest_repo_async(repo_name: str, trigger: str) -> Dict[str, Any]:
    # Celery is prefork: each worker process should keep its own pool alive across tasks.
    # This avoids connection pool churn and speeds up bulk harvests.
    if not database.is_connected:
        await database.connect()
    logger.info("OGM harvest starting: repo=%s trigger=%s", repo_name, trigger)
    return await harvest_repo(repo_name=repo_name, trigger=trigger)


@celery_app.task(
    bind=True,
    name="ogm_harvest_all",
    soft_time_limit=10 * 60,  # 10 minutes
    time_limit=15 * 60,  # 15 minutes
)
def ogm_harvest_all(self, trigger: str = "weekly") -> Dict[str, Any]:
    """Enqueue harvest jobs for all enabled repos (watch_mode weekly/both)."""
    return _run(_ogm_harvest_all_async(trigger=trigger))


async def _ogm_harvest_all_async(trigger: str) -> Dict[str, Any]:
    # Celery is prefork: each worker process should keep its own pool alive across tasks.
    if not database.is_connected:
        await database.connect()
    repo = OGMHarvestRepository()
    repos = await repo.list_repos()
    selected = []
    for r in repos:
        if not r.get("ogm_enabled", True):
            continue
        mode = (r.get("ogm_watch_mode") or "").lower()
        if trigger == "weekly" and mode not in {"weekly", "both"}:
            continue
        selected.append(r["ogm_repo_name"])

    task_ids: List[str] = []
    for name in selected:
        task = ogm_harvest_repo.delay(repo_name=name, trigger=trigger)
        task_ids.append(task.id)

    return {"enqueued": len(task_ids), "repo_names": selected, "task_ids": task_ids}

