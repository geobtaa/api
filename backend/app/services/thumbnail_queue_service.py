from __future__ import annotations

import hashlib
import logging
import os

import redis

logger = logging.getLogger(__name__)

_queue_cache = redis.Redis(
    host=os.getenv("REDIS_HOST", "redis"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    password=os.getenv("REDIS_PASSWORD"),
    db=0,
    decode_responses=True,
)


def _queue_ttl_seconds() -> int:
    return int(os.getenv("THUMBNAIL_QUEUE_DEDUPE_TTL_SECONDS", "300"))


def thumbnail_queue_slot_key(resource_id: str | None, source_url: str) -> str:
    digest = hashlib.sha256(f"{resource_id or ''}:{source_url}".encode()).hexdigest()
    return f"thumbnail_queue_slot:{digest}"


def acquire_thumbnail_queue_slot(resource_id: str | None, source_url: str) -> bool:
    key = thumbnail_queue_slot_key(resource_id, source_url)
    try:
        return bool(_queue_cache.set(key, "1", ex=_queue_ttl_seconds(), nx=True))
    except Exception as exc:
        logger.debug("Thumbnail queue dedupe unavailable for %s: %s", key, exc)
        return True


def release_thumbnail_queue_slot(resource_id: str | None, source_url: str) -> None:
    key = thumbnail_queue_slot_key(resource_id, source_url)
    try:
        _queue_cache.delete(key)
    except Exception as exc:
        logger.debug("Failed to release thumbnail queue slot %s: %s", key, exc)
