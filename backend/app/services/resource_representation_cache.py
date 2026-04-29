import copy
import os
from collections.abc import Awaitable, Callable, Iterable
from typing import Any

from app.services.cache_service import CacheService

RESOURCE_REPRESENTATION_CACHE_VERSION = os.getenv("RESOURCE_REPRESENTATION_CACHE_VERSION", "v1")
RESOURCE_REPRESENTATION_CACHE_TTL = int(
    os.getenv("RESOURCE_REPRESENTATION_CACHE_TTL", os.getenv("RESOURCE_CACHE_TTL", "86400"))
)
RESOURCE_REPRESENTATION_NAMESPACE = "resource_representation"
RESOURCE_REPRESENTATION_PROFILE = "api-full"

ResourceBuilder = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


def resource_representation_cache_key(resource_id: str, *, profile: str) -> str:
    return CacheService.generate_cache_key(
        RESOURCE_REPRESENTATION_NAMESPACE,
        version=RESOURCE_REPRESENTATION_CACHE_VERSION,
        profile=profile,
        resource_id=resource_id,
    )


def _copy_resource(resource: dict[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(resource)


async def get_cached_resource_representations(
    resource_ids: Iterable[str],
    *,
    profile: str = RESOURCE_REPRESENTATION_PROFILE,
    cache_service: CacheService | None = None,
) -> dict[str, dict[str, Any]]:
    """Return cached JSON:API resource objects keyed by resource id."""
    ids = [str(resource_id) for resource_id in resource_ids if resource_id]
    if not ids:
        return {}

    cache_service = cache_service or CacheService()
    key_by_id = {
        resource_id: resource_representation_cache_key(resource_id, profile=profile)
        for resource_id in ids
    }
    cached_by_key = await cache_service.get_many(key_by_id.values())

    cached_by_id: dict[str, dict[str, Any]] = {}
    for resource_id, key in key_by_id.items():
        cached = cached_by_key.get(key)
        if isinstance(cached, dict):
            cached_by_id[resource_id] = _copy_resource(cached)
    return cached_by_id


async def store_resource_representation(
    resource_id: str,
    resource: dict[str, Any],
    *,
    profile: str = RESOURCE_REPRESENTATION_PROFILE,
    cache_service: CacheService | None = None,
    ttl: int = RESOURCE_REPRESENTATION_CACHE_TTL,
) -> None:
    """Store a resource representation and tag it for resource invalidation."""
    if not resource_id or not isinstance(resource, dict):
        return

    cache_service = cache_service or CacheService()
    key = resource_representation_cache_key(resource_id, profile=profile)
    if not await cache_service.set(key, resource, ttl=ttl):
        return

    await cache_service.tag_cache_key(
        key,
        {
            "resource",
            RESOURCE_REPRESENTATION_NAMESPACE,
            f"resource:{resource_id}",
            f"resource-representation:{profile}",
        },
        ttl_seconds=ttl,
    )


async def get_or_build_resource_representation(
    resource_dict: dict[str, Any],
    builder: ResourceBuilder,
    *,
    profile: str = RESOURCE_REPRESENTATION_PROFILE,
    cache_service: CacheService | None = None,
) -> dict[str, Any]:
    """Get a cached resource object, building and storing it on a miss."""
    resource_id = str(resource_dict.get("id") or "")
    if not resource_id:
        return await builder(resource_dict)

    cached = await get_cached_resource_representations(
        [resource_id],
        profile=profile,
        cache_service=cache_service,
    )
    if resource_id in cached:
        return cached[resource_id]

    resource = await builder(resource_dict)
    await store_resource_representation(
        resource_id,
        resource,
        profile=profile,
        cache_service=cache_service,
    )
    return _copy_resource(resource)
