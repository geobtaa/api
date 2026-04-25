from __future__ import annotations

import asyncio
import logging
import os
import re
from typing import Optional

import redis

from app.services.visual_asset_cache import cache_visual_asset

logger = logging.getLogger(__name__)

THUMBNAIL_HASH_RE = re.compile(r"^[0-9a-f]{64}$", re.IGNORECASE)
THUMBNAIL_ALIAS_PREFIX = "thumbnail_alias"

_redis_alias_connection_pool = None


def is_thumbnail_hash(value: str | None) -> bool:
    """Return True when the value looks like an immutable thumbnail content hash."""
    if not value:
        return False
    return bool(THUMBNAIL_HASH_RE.fullmatch(value))


def _get_redis_alias_connection_pool():
    """Get or create shared Redis connection pool for thumbnail aliases (db=0)."""
    global _redis_alias_connection_pool
    if _redis_alias_connection_pool is None:
        _redis_alias_connection_pool = redis.ConnectionPool(
            host=os.getenv("REDIS_HOST", "redis"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            password=os.getenv("REDIS_PASSWORD"),
            db=0,
            decode_responses=True,
            max_connections=20,
            socket_connect_timeout=1.0,
            socket_timeout=1.0,
        )
    return _redis_alias_connection_pool


class ThumbnailAliasService:
    """Fast resource_id -> immutable thumbnail hash lookup backed by Redis."""

    def __init__(self) -> None:
        self.cache = redis.Redis(connection_pool=_get_redis_alias_connection_pool())
        self.ttl_seconds = int(os.getenv("THUMBNAIL_ALIAS_TTL_SECONDS", "0"))

    def _key(self, resource_id: str) -> str:
        return f"{THUMBNAIL_ALIAS_PREFIX}:{resource_id}"

    def get_hash_sync(self, resource_id: str) -> Optional[str]:
        """Return the cached immutable thumbnail hash for a resource, if present."""
        try:
            value = self.cache.get(self._key(resource_id))
            if is_thumbnail_hash(value):
                return value
            if value:
                self.cache.delete(self._key(resource_id))
            return None
        except Exception as exc:
            logger.warning("Failed to read thumbnail alias for %s: %s", resource_id, exc)
            return None

    async def get_hash(self, resource_id: str) -> Optional[str]:
        return await asyncio.to_thread(self.get_hash_sync, resource_id)

    def set_hash_sync(self, resource_id: str, image_hash: str) -> bool:
        """Cache the immutable thumbnail hash for a resource."""
        if not is_thumbnail_hash(image_hash):
            return False
        try:
            if self.ttl_seconds > 0:
                return bool(self.cache.setex(self._key(resource_id), self.ttl_seconds, image_hash))
            return cache_visual_asset(self.cache, self._key(resource_id), image_hash)
        except Exception as exc:
            logger.warning(
                "Failed to cache thumbnail alias for %s -> %s: %s",
                resource_id,
                image_hash,
                exc,
            )
            return False

    async def set_hash(self, resource_id: str, image_hash: str) -> bool:
        return await asyncio.to_thread(self.set_hash_sync, resource_id, image_hash)

    def delete_sync(self, resource_id: str) -> bool:
        """Remove a resource thumbnail alias from Redis."""
        try:
            return bool(self.cache.delete(self._key(resource_id)))
        except Exception as exc:
            logger.warning("Failed to delete thumbnail alias for %s: %s", resource_id, exc)
            return False

    async def delete(self, resource_id: str) -> bool:
        return await asyncio.to_thread(self.delete_sync, resource_id)


thumbnail_alias_service = ThumbnailAliasService()
