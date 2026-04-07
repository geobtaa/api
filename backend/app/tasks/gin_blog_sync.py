import asyncio
import logging
from typing import Any, Dict, Optional

from app.services.cache_service import CacheService
from app.services.gin_blog_service import GINBlogService
from app.tasks.worker import celery_app
from db.database import database

logger = logging.getLogger(__name__)

_loop: Optional[asyncio.AbstractEventLoop] = None
HOME_BLOG_CACHE_TAGS = ["home", "home_blog"]


def _get_loop() -> asyncio.AbstractEventLoop:
    global _loop
    if _loop is None or _loop.is_closed():
        _loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_loop)
    return _loop


def _run(coro):
    return _get_loop().run_until_complete(coro)


@celery_app.task(
    bind=True,
    name="gin_blog_sync",
    soft_time_limit=10 * 60,
    time_limit=15 * 60,
)
def gin_blog_sync(self) -> Dict[str, Any]:
    return _run(run_gin_blog_sync())


async def run_gin_blog_sync() -> Dict[str, Any]:
    if not database.is_connected:
        await database.connect()
    logger.info("GIN blog sync starting")
    service = GINBlogService()
    result = await service.sync_posts_from_github()
    try:
        deleted = await CacheService().invalidate_tags(HOME_BLOG_CACHE_TAGS)
        logger.info(
            "GIN blog sync invalidated cache tags %s (deleted=%s)",
            HOME_BLOG_CACHE_TAGS,
            deleted,
        )
    except Exception as exc:
        logger.warning("GIN blog sync completed but cache invalidation failed: %s", exc)
    logger.info("GIN blog sync completed: %s", result)
    return result
