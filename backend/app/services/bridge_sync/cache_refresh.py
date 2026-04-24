from __future__ import annotations

import logging
import os
from typing import Any, Iterable

import httpx

from app.services.cache_service import ENDPOINT_CACHE, CacheService

logger = logging.getLogger(__name__)

DEFAULT_REWARM_RESOURCE_PATHS = ("/api/v1/resources/{id}",)


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "t", "yes", "y"}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        logger.warning("Invalid integer for %s=%r; using default=%s", name, value, default)
        return default


def _dedupe_preserve_order(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = str(value or "").strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned)
    return result


def _warm_path_from_record(record: dict[str, Any]) -> str | None:
    warm = record.get("warm")
    if not isinstance(warm, dict):
        return None
    if str(warm.get("method") or "GET").upper() != "GET":
        return None
    path = str(warm.get("path") or "").strip()
    if not path.startswith("/"):
        return None
    query = str(warm.get("query") or "").strip()
    return f"{path}?{query}" if query else path


def _default_resource_warm_paths(resource_ids: Iterable[str]) -> list[str]:
    paths: list[str] = []
    for resource_id in resource_ids:
        for template in DEFAULT_REWARM_RESOURCE_PATHS:
            paths.append(template.format(id=resource_id))
    return paths


async def refresh_cache_for_changed_resources(
    resource_ids: Iterable[str],
) -> dict[str, Any]:
    """
    Invalidate and re-warm cached public pages tagged with changed resource IDs.

    Cached search/resource responses record their public GET path/query when stored.
    After a bridge delta import, we collect those paths from `resource:<id>` tags,
    purge the old entries, then replay the GETs through the in-process FastAPI app so
    the same cache decorators repopulate Redis without depending on public self-HTTP.
    """

    if not ENDPOINT_CACHE or not _env_bool("BRIDGE_CACHE_REFRESH_ENABLED", True):
        return {"enabled": False, "resource_ids": 0, "invalidated": 0, "warmed": 0, "errors": 0}

    max_resource_ids = _env_int("BRIDGE_CACHE_REFRESH_MAX_RESOURCE_IDS", 5000)
    max_warm_urls = _env_int("BRIDGE_CACHE_REWARM_MAX_URLS", 2500)
    request_timeout = float(os.getenv("BRIDGE_CACHE_REWARM_TIMEOUT_SECONDS", "20"))

    changed_ids = _dedupe_preserve_order(resource_ids)[:max_resource_ids]
    if not changed_ids:
        return {"enabled": True, "resource_ids": 0, "invalidated": 0, "warmed": 0, "errors": 0}

    tags = [f"resource:{rid}" for rid in changed_ids]
    cache = CacheService()

    tagged_records = await cache.cached_records_for_tags(tags)
    tagged_paths = [_warm_path_from_record(record) for record in tagged_records]
    warm_paths = _dedupe_preserve_order(
        [
            *[path for path in tagged_paths if path],
            *_default_resource_warm_paths(changed_ids),
        ]
    )[:max_warm_urls]

    invalidated = await cache.invalidate_tags(tags)

    warmed = 0
    errors = 0
    if warm_paths:
        # Import lazily to avoid initializing the FastAPI app during module import.
        from app.main import app

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://bridge-cache-refresh.local",
            timeout=request_timeout,
        ) as client:
            for path in warm_paths:
                try:
                    response = await client.get(path, headers={"Accept": "application/json"})
                    if 200 <= response.status_code < 300:
                        warmed += 1
                    else:
                        errors += 1
                        logger.warning(
                            "Bridge cache rewarm returned status=%s path=%s",
                            response.status_code,
                            path,
                        )
                except Exception as exc:
                    errors += 1
                    logger.warning("Bridge cache rewarm failed path=%s err=%s", path, exc)

    stats = {
        "enabled": True,
        "resource_ids": len(changed_ids),
        "tagged_records": len(tagged_records),
        "warm_urls": len(warm_paths),
        "invalidated": invalidated,
        "warmed": warmed,
        "errors": errors,
    }
    logger.info("Bridge cache refresh complete: %s", stats)
    return stats
