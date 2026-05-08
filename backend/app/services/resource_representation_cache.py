import copy
import hashlib
import json
import logging
import os
from collections.abc import Awaitable, Callable, Iterable
from datetime import datetime
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.services.cache_service import CacheService
from app.services.distribution_repository import async_session_factory
from db.models import generated_resource_representations

RESOURCE_REPRESENTATION_CACHE_VERSION = os.getenv("RESOURCE_REPRESENTATION_CACHE_VERSION", "v1")
RESOURCE_REPRESENTATION_CACHE_TTL = int(
    os.getenv("RESOURCE_REPRESENTATION_CACHE_TTL", os.getenv("RESOURCE_CACHE_TTL", "86400"))
)
RESOURCE_REPRESENTATION_NAMESPACE = "resource_representation"
RESOURCE_REPRESENTATION_PROFILE = "api-full"
RESOURCE_SEARCH_RESULT_REPRESENTATION_PROFILE = "search-result"
RESOURCE_REPRESENTATION_DURABLE_STORE = os.getenv(
    "RESOURCE_REPRESENTATION_DURABLE_STORE", "database"
).lower()
RESOURCE_REPRESENTATION_BULK_STORE_BATCH_SIZE = int(
    os.getenv("RESOURCE_REPRESENTATION_BULK_STORE_BATCH_SIZE", "250")
)

logger = logging.getLogger(__name__)

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


def _chunk_dict(
    values: dict[str, dict[str, Any]], batch_size: int
) -> Iterable[dict[str, dict[str, Any]]]:
    items = list(values.items())
    size = max(1, batch_size)
    for index in range(0, len(items), size):
        yield dict(items[index : index + size])


def durable_resource_representations_enabled() -> bool:
    return RESOURCE_REPRESENTATION_DURABLE_STORE == "database"


def _json_safe_resource(resource: dict[str, Any]) -> dict[str, Any]:
    """Normalize generated representations to values PostgreSQL JSON can store."""
    return json.loads(json.dumps(resource, default=str))


def _payload_metadata(resource: dict[str, Any]) -> tuple[dict[str, Any], str, int]:
    payload = _json_safe_resource(resource)
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return payload, hashlib.sha256(raw).hexdigest(), len(raw)


def _resource_representation_tags(resource_id: str, profile: str) -> set[str]:
    return {
        "resource",
        RESOURCE_REPRESENTATION_NAMESPACE,
        f"resource:{resource_id}",
        f"resource-representation:{profile}",
    }


async def _store_redis_resource_representation(
    resource_id: str,
    resource: dict[str, Any],
    *,
    profile: str,
    cache_service: CacheService,
    ttl: int,
) -> bool:
    key = resource_representation_cache_key(resource_id, profile=profile)
    if not await cache_service.set(key, resource, ttl=ttl):
        return False

    await cache_service.tag_cache_key(
        key,
        _resource_representation_tags(resource_id, profile),
        ttl_seconds=ttl,
    )
    return True


async def _rehydrate_redis_resource_representations(
    resources_by_id: dict[str, dict[str, Any]],
    *,
    profile: str,
    cache_service: CacheService,
    ttl: int,
) -> None:
    if not resources_by_id:
        return

    values = {
        resource_representation_cache_key(resource_id, profile=profile): resource
        for resource_id, resource in resources_by_id.items()
    }
    if not await cache_service.set_many(values, ttl=ttl):
        return

    for resource_id in resources_by_id:
        key = resource_representation_cache_key(resource_id, profile=profile)
        await cache_service.tag_cache_key(
            key,
            _resource_representation_tags(resource_id, profile),
            ttl_seconds=ttl,
        )


async def _store_redis_resource_representations(
    resources_by_id: dict[str, dict[str, Any]],
    *,
    profile: str,
    cache_service: CacheService,
    ttl: int,
) -> bool:
    if not resources_by_id:
        return True

    values = {
        resource_representation_cache_key(resource_id, profile=profile): resource
        for resource_id, resource in resources_by_id.items()
    }
    if not await cache_service.set_many(values, ttl=ttl):
        return False

    for resource_id in resources_by_id:
        key = resource_representation_cache_key(resource_id, profile=profile)
        await cache_service.tag_cache_key(
            key,
            _resource_representation_tags(resource_id, profile),
            ttl_seconds=ttl,
        )
    return True


async def get_durable_resource_representations(
    resource_ids: Iterable[str],
    *,
    profile: str = RESOURCE_REPRESENTATION_PROFILE,
    version: str = RESOURCE_REPRESENTATION_CACHE_VERSION,
) -> dict[str, dict[str, Any]]:
    """Load durable generated resource representations from PostgreSQL."""
    ids = list(dict.fromkeys(str(resource_id) for resource_id in resource_ids if resource_id))
    if not ids or not durable_resource_representations_enabled():
        return {}

    stmt = select(
        generated_resource_representations.c.resource_id,
        generated_resource_representations.c.payload,
    ).where(
        generated_resource_representations.c.resource_id.in_(ids),
        generated_resource_representations.c.profile == profile,
        generated_resource_representations.c.version == version,
    )

    try:
        async with async_session_factory() as session:
            result = await session.execute(stmt)
            rows = result.fetchall()
    except Exception as exc:
        logger.warning("Failed to load durable resource representations: %s", exc)
        return {}

    cached_by_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        payload = row._mapping["payload"]
        if isinstance(payload, dict):
            cached_by_id[str(row._mapping["resource_id"])] = _copy_resource(payload)
    return cached_by_id


async def store_durable_resource_representation(
    resource_id: str,
    resource: dict[str, Any],
    *,
    profile: str = RESOURCE_REPRESENTATION_PROFILE,
    version: str = RESOURCE_REPRESENTATION_CACHE_VERSION,
    source_updated_at: datetime | None = None,
) -> bool:
    """Persist a generated resource representation so Redis can be rehydrated."""
    if not resource_id or not isinstance(resource, dict):
        return False
    if not durable_resource_representations_enabled():
        return False

    payload, payload_hash, payload_byte_size = _payload_metadata(resource)
    values = {
        "resource_id": resource_id,
        "profile": profile,
        "version": version,
        "payload": payload,
        "payload_hash": payload_hash,
        "payload_byte_size": payload_byte_size,
        "source_updated_at": source_updated_at,
    }
    stmt = pg_insert(generated_resource_representations).values(**values)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_generated_resource_representations_identity",
        set_={
            "payload": stmt.excluded.payload,
            "payload_hash": stmt.excluded.payload_hash,
            "payload_byte_size": stmt.excluded.payload_byte_size,
            "source_updated_at": stmt.excluded.source_updated_at,
            "generated_at": func.now(),
        },
    )

    try:
        async with async_session_factory() as session:
            async with session.begin():
                await session.execute(stmt)
        return True
    except Exception as exc:
        logger.warning("Failed to persist durable resource representation %s: %s", resource_id, exc)
        return False


async def store_durable_resource_representations(
    resources_by_id: dict[str, dict[str, Any]],
    *,
    profile: str = RESOURCE_REPRESENTATION_PROFILE,
    version: str = RESOURCE_REPRESENTATION_CACHE_VERSION,
    source_updated_at_by_id: dict[str, datetime | None] | None = None,
) -> bool:
    """Bulk persist generated representations so priming avoids one upsert per resource."""
    if not durable_resource_representations_enabled():
        return False

    rows: list[dict[str, Any]] = []
    source_updated_at_by_id = source_updated_at_by_id or {}
    for resource_id, resource in resources_by_id.items():
        if not resource_id or not isinstance(resource, dict):
            continue
        payload, payload_hash, payload_byte_size = _payload_metadata(resource)
        rows.append(
            {
                "resource_id": resource_id,
                "profile": profile,
                "version": version,
                "payload": payload,
                "payload_hash": payload_hash,
                "payload_byte_size": payload_byte_size,
                "source_updated_at": source_updated_at_by_id.get(resource_id),
            }
        )

    if not rows:
        return False

    try:
        async with async_session_factory() as session:
            async with session.begin():
                size = max(1, RESOURCE_REPRESENTATION_BULK_STORE_BATCH_SIZE)
                for index in range(0, len(rows), size):
                    row_batch = rows[index : index + size]
                    stmt = pg_insert(generated_resource_representations).values(row_batch)
                    stmt = stmt.on_conflict_do_update(
                        constraint="uq_generated_resource_representations_identity",
                        set_={
                            "payload": stmt.excluded.payload,
                            "payload_hash": stmt.excluded.payload_hash,
                            "payload_byte_size": stmt.excluded.payload_byte_size,
                            "source_updated_at": stmt.excluded.source_updated_at,
                            "generated_at": func.now(),
                        },
                    )
                    await session.execute(stmt)
        return True
    except Exception as exc:
        logger.warning("Failed to bulk persist durable resource representations: %s", exc)
        return False


async def delete_durable_resource_representations(
    resource_ids: Iterable[str] | None = None,
    *,
    profile: str | None = None,
    version: str | None = None,
) -> bool:
    """Delete durable generated representations during explicit resource cache clears."""
    if not durable_resource_representations_enabled():
        return False

    stmt = delete(generated_resource_representations)
    ids = list(
        dict.fromkeys(str(resource_id) for resource_id in (resource_ids or []) if resource_id)
    )
    if ids:
        stmt = stmt.where(generated_resource_representations.c.resource_id.in_(ids))
    if profile:
        stmt = stmt.where(generated_resource_representations.c.profile == profile)
    if version:
        stmt = stmt.where(generated_resource_representations.c.version == version)

    try:
        async with async_session_factory() as session:
            async with session.begin():
                await session.execute(stmt)
        return True
    except Exception as exc:
        logger.warning("Failed to delete durable resource representations: %s", exc)
        return False


async def get_cached_resource_representations(
    resource_ids: Iterable[str],
    *,
    profile: str = RESOURCE_REPRESENTATION_PROFILE,
    cache_service: CacheService | None = None,
    ttl: int = RESOURCE_REPRESENTATION_CACHE_TTL,
    read_durable: bool = True,
) -> dict[str, dict[str, Any]]:
    """Return cached JSON:API resource objects keyed by resource id."""
    ids = list(dict.fromkeys(str(resource_id) for resource_id in resource_ids if resource_id))
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

    missing_ids = [resource_id for resource_id in ids if resource_id not in cached_by_id]
    if missing_ids and read_durable:
        durable_by_id = await get_durable_resource_representations(
            missing_ids,
            profile=profile,
        )
        if durable_by_id:
            await _rehydrate_redis_resource_representations(
                durable_by_id,
                profile=profile,
                cache_service=cache_service,
                ttl=ttl,
            )
            for resource_id, resource in durable_by_id.items():
                cached_by_id[resource_id] = _copy_resource(resource)
    return cached_by_id


async def store_resource_representation(
    resource_id: str,
    resource: dict[str, Any],
    *,
    profile: str = RESOURCE_REPRESENTATION_PROFILE,
    cache_service: CacheService | None = None,
    ttl: int = RESOURCE_REPRESENTATION_CACHE_TTL,
    write_durable: bool = True,
    source_updated_at: datetime | None = None,
) -> None:
    """Store a resource representation and tag it for resource invalidation."""
    if not resource_id or not isinstance(resource, dict):
        return

    cache_service = cache_service or CacheService()
    payload = _json_safe_resource(resource)
    if write_durable:
        await store_durable_resource_representation(
            resource_id,
            payload,
            profile=profile,
            source_updated_at=source_updated_at,
        )
    await _store_redis_resource_representation(
        resource_id,
        payload,
        profile=profile,
        cache_service=cache_service,
        ttl=ttl,
    )


async def store_resource_representations(
    resources_by_id: dict[str, dict[str, Any]],
    *,
    profile: str = RESOURCE_REPRESENTATION_PROFILE,
    cache_service: CacheService | None = None,
    ttl: int = RESOURCE_REPRESENTATION_CACHE_TTL,
    write_durable: bool = True,
    source_updated_at_by_id: dict[str, datetime | None] | None = None,
) -> None:
    """Bulk store generated representations in durable storage and Redis."""
    valid_payloads = {
        str(resource_id): _json_safe_resource(resource)
        for resource_id, resource in resources_by_id.items()
        if resource_id and isinstance(resource, dict)
    }
    if not valid_payloads:
        return

    cache_service = cache_service or CacheService()
    for payload_batch in _chunk_dict(
        valid_payloads, RESOURCE_REPRESENTATION_BULK_STORE_BATCH_SIZE
    ):
        if write_durable:
            batch_source_updated_at = {
                resource_id: source_updated_at
                for resource_id, source_updated_at in (source_updated_at_by_id or {}).items()
                if resource_id in payload_batch
            }
            await store_durable_resource_representations(
                payload_batch,
                profile=profile,
                source_updated_at_by_id=batch_source_updated_at,
            )
        await _store_redis_resource_representations(
            payload_batch,
            profile=profile,
            cache_service=cache_service,
            ttl=ttl,
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
