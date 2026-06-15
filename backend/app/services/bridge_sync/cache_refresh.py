from __future__ import annotations

import asyncio
import logging
import os
from collections import Counter
from typing import Any, Iterable

import httpx
from sqlalchemy import select

from app.api.v1.utils import sanitize_for_json
from app.services.cache_service import ENDPOINT_CACHE, CacheService
from app.services.distribution_repository import async_session_factory
from app.services.resource_representation_cache import delete_resource_representations
from db.models import resources

logger = logging.getLogger(__name__)

DEFAULT_REWARM_RESOURCE_PATHS = ("/api/v1/resources/{id}",)
DEFAULT_REFRESH_BATCH_SIZE = 5000


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


def _positive_env_int(name: str, default: int) -> int:
    value = _env_int(name, default)
    if value < 1:
        logger.warning(
            "Invalid non-positive integer for %s=%r; using default=%s", name, value, default
        )
        return default
    return value


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


def _refresh_batch_size() -> int:
    # BRIDGE_CACHE_REFRESH_MAX_RESOURCE_IDS used to be a total cap. Keep it as
    # a compatibility alias, but interpret it as batch size so no IDs are lost.
    legacy_batch_size = _positive_env_int(
        "BRIDGE_CACHE_REFRESH_MAX_RESOURCE_IDS", DEFAULT_REFRESH_BATCH_SIZE
    )
    return _positive_env_int("BRIDGE_CACHE_REFRESH_BATCH_SIZE", legacy_batch_size)


def _chunk_list(values: list[str], size: int) -> Iterable[list[str]]:
    for start in range(0, len(values), size):
        yield values[start : start + size]


def _merge_numeric_stats(total: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
    merged = dict(total)
    for key, value in update.items():
        if isinstance(value, bool):
            merged[key] = bool(merged.get(key, True)) and value if key == "enabled" else value
        elif isinstance(value, (int, float)):
            merged[key] = merged.get(key, 0) + value
        elif isinstance(value, dict):
            existing = merged.get(key) if isinstance(merged.get(key), dict) else {}
            merged[key] = _merge_numeric_stats(existing, value)
        elif key not in merged:
            merged[key] = value
    return merged


def _merge_representation_delete_stats(
    total: dict[str, Any] | None,
    update: dict[str, Any],
) -> dict[str, Any]:
    merged = dict(total or {})
    if "durable_deleted" in update:
        merged["durable_deleted"] = bool(merged.get("durable_deleted", True)) and bool(
            update.get("durable_deleted")
        )
    if "redis_deleted" in update:
        merged["redis_deleted"] = int(merged.get("redis_deleted", 0)) + int(
            update.get("redis_deleted") or 0
        )
    return merged


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


async def _fetch_changed_resource_dicts(resource_ids: Iterable[str]) -> list[dict[str, Any]]:
    ids = _dedupe_preserve_order(resource_ids)
    if not ids:
        return []

    async with async_session_factory() as session:
        stmt = select(resources).where(resources.c.id.in_(ids))
        result = await session.execute(stmt)
        return [sanitize_for_json(dict(row._mapping)) for row in result.fetchall()]


async def _prime_thumbnail_caches(
    resource_dicts: list[dict[str, Any]],
    *,
    concurrency: int,
    force: bool,
) -> dict[str, Any]:
    if not resource_dicts:
        return {"attempted": 0}

    from scripts.prime_thumbnail_cache import _prime_thumbnail_for_resource

    counters: Counter[str] = Counter()
    semaphore = asyncio.Semaphore(max(1, concurrency))

    async def run_one(resource_dict: dict[str, Any]) -> tuple[str, str, str]:
        async with semaphore:
            return await _prime_thumbnail_for_resource(
                resource_dict,
                force=force,
                retry_failures=True,
                retry_placeheld=True,
            )

    tasks = [asyncio.create_task(run_one(resource_dict)) for resource_dict in resource_dicts]
    for task in asyncio.as_completed(tasks):
        status, _resource_id, _detail = await task
        counters[status] += 1

    return {"attempted": len(resource_dicts), **dict(counters)}


async def _prime_static_map_caches(
    resource_dicts: list[dict[str, Any]],
    *,
    concurrency: int,
    force: bool,
) -> dict[str, Any]:
    if not resource_dicts:
        return {"attempted": 0}

    from scripts.prime_static_map_cache import _prime_static_maps_for_resource

    counters: Counter[str] = Counter()
    semaphore = asyncio.Semaphore(max(1, concurrency))

    async def run_one(resource_dict: dict[str, Any]) -> tuple[str, str, str]:
        async with semaphore:
            return await _prime_static_maps_for_resource(
                resource_dict,
                force=force,
                hydrate_assets=False,
            )

    tasks = [asyncio.create_task(run_one(resource_dict)) for resource_dict in resource_dicts]
    for task in asyncio.as_completed(tasks):
        status, _resource_id, _detail = await task
        counters[status] += 1

    return {"attempted": len(resource_dicts), **dict(counters)}


async def _prime_resource_class_icon_cache(
    resource_dict: dict[str, Any],
    *,
    force: bool,
) -> tuple[str, str]:
    from app.api.v1.endpoint_modules.resources.thumbnail import (
        _resource_class_icon_signature,
        _svg_icon_bytes_for_resource,
    )
    from app.services.static_map_service import StaticMapService

    resource_id = str(resource_dict.get("id") or "")
    if not resource_id:
        return ("failed", "missing resource id")

    map_service = StaticMapService()
    source_signature = _resource_class_icon_signature(
        resource_dict,
        variant="icon-basemap",
    )
    if not force:
        cached_hash = await asyncio.to_thread(
            map_service.materialize_cached_variant_sync,
            resource_id,
            variant="resource-class-icon",
            source_signature=source_signature,
        )
        if cached_hash:
            return ("cached", resource_id)

    try:
        svg_bytes = await _svg_icon_bytes_for_resource(
            resource_dict,
            variant="icon-basemap",
        )
        map_hash = await map_service.materialize_asset(
            resource_id,
            variant="resource-class-icon",
            map_bytes=svg_bytes,
            source_signature=source_signature,
        )
        return ("generated" if map_hash else "failed", resource_id)
    except Exception as exc:
        logger.warning("Bridge resource-class icon refresh failed for %s: %s", resource_id, exc)
        return ("failed", resource_id)


async def _prime_resource_class_icon_caches(
    resource_dicts: list[dict[str, Any]],
    *,
    concurrency: int,
    force: bool,
) -> dict[str, Any]:
    if not resource_dicts:
        return {"attempted": 0}

    counters: Counter[str] = Counter()
    semaphore = asyncio.Semaphore(max(1, concurrency))

    async def run_one(resource_dict: dict[str, Any]) -> tuple[str, str]:
        async with semaphore:
            return await _prime_resource_class_icon_cache(resource_dict, force=force)

    tasks = [asyncio.create_task(run_one(resource_dict)) for resource_dict in resource_dicts]
    for task in asyncio.as_completed(tasks):
        status, _resource_id = await task
        counters[status] += 1

    return {"attempted": len(resource_dicts), **dict(counters)}


async def _warm_generated_assets_for_changed_resources(
    resource_ids: Iterable[str],
) -> dict[str, Any]:
    if not _env_bool("BRIDGE_GENERATED_ASSET_REFRESH_ENABLED", True):
        return {"enabled": False}

    resource_dicts = await _fetch_changed_resource_dicts(resource_ids)
    if not resource_dicts:
        return {"enabled": True, "resources": 0}

    thumbnail_concurrency = _env_int("BRIDGE_CACHE_THUMBNAIL_CONCURRENCY", 2)
    static_map_concurrency = _env_int("BRIDGE_CACHE_STATIC_MAP_CONCURRENCY", 2)
    icon_concurrency = _env_int("BRIDGE_CACHE_RESOURCE_ICON_CONCURRENCY", 4)
    force = _env_bool("BRIDGE_CACHE_REFRESH_FORCE_GENERATED_ASSETS", True)

    thumbnail_stats = await _prime_thumbnail_caches(
        resource_dicts,
        concurrency=thumbnail_concurrency,
        force=force,
    )
    static_map_stats = await _prime_static_map_caches(
        resource_dicts,
        concurrency=static_map_concurrency,
        force=force,
    )
    resource_icon_stats = await _prime_resource_class_icon_caches(
        resource_dicts,
        concurrency=icon_concurrency,
        force=force,
    )

    return {
        "enabled": True,
        "resources": len(resource_dicts),
        "thumbnails": thumbnail_stats,
        "static_maps": static_map_stats,
        "resource_class_icons": resource_icon_stats,
    }


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

    max_warm_urls = _env_int("BRIDGE_CACHE_REWARM_MAX_URLS", 2500)
    request_timeout = float(os.getenv("BRIDGE_CACHE_REWARM_TIMEOUT_SECONDS", "20"))

    changed_ids = _dedupe_preserve_order(resource_ids)
    if not changed_ids:
        return {"enabled": True, "resource_ids": 0, "invalidated": 0, "warmed": 0, "errors": 0}

    batch_size = _refresh_batch_size()
    cache = CacheService()
    warm_paths: list[str] = []
    warm_path_seen: set[str] = set()

    def add_warm_path(path: str | None) -> None:
        if max_warm_urls <= 0 or len(warm_paths) >= max_warm_urls:
            return
        if not path or path in warm_path_seen:
            return
        warm_path_seen.add(path)
        warm_paths.append(path)

    tagged_records_count = 0
    representation_delete_stats: dict[str, Any] | None = None
    generated_assets: dict[str, Any] = {}
    invalidated = 0
    batches = 0

    for batch_ids in _chunk_list(changed_ids, batch_size):
        batches += 1
        tags = [f"resource:{rid}" for rid in batch_ids]

        tagged_records = await cache.cached_records_for_tags(tags)
        tagged_records_count += len(tagged_records)
        for record in tagged_records:
            add_warm_path(_warm_path_from_record(record))
        for path in _default_resource_warm_paths(batch_ids):
            add_warm_path(path)

        batch_representation_delete_stats = await delete_resource_representations(
            batch_ids,
            cache_service=cache,
        )
        representation_delete_stats = _merge_representation_delete_stats(
            representation_delete_stats,
            batch_representation_delete_stats,
        )

        invalidated += await cache.invalidate_tags(tags)
        batch_generated_assets = await _warm_generated_assets_for_changed_resources(batch_ids)
        generated_assets = _merge_numeric_stats(generated_assets, batch_generated_assets)

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
        "batch_size": batch_size,
        "batches": batches,
        "tagged_records": tagged_records_count,
        "warm_urls": len(warm_paths),
        "resource_representations_deleted": representation_delete_stats or {},
        "generated_assets": generated_assets,
        "invalidated": invalidated,
        "warmed": warmed,
        "errors": errors,
    }
    logger.info("Bridge cache refresh complete: %s", stats)
    return stats
