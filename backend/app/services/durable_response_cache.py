import base64
import hashlib
import json
import logging
import os
from datetime import datetime
from typing import Any, Iterable

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.services.distribution_repository import async_session_factory
from db.models import generated_api_response_tags, generated_api_responses

logger = logging.getLogger(__name__)

API_RESPONSE_DURABLE_CACHE_STORE = os.getenv(
    "API_RESPONSE_DURABLE_CACHE_STORE",
    "database",
).lower()


def durable_api_response_cache_enabled() -> bool:
    return API_RESPONSE_DURABLE_CACHE_STORE == "database"


def _epoch_to_datetime(value: Any) -> datetime | None:
    try:
        return datetime.utcfromtimestamp(float(value))
    except (TypeError, ValueError, OSError, OverflowError):
        return None


def _json_safe_record(record: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(record, default=str))


def _record_metadata(record: dict[str, Any]) -> tuple[dict[str, Any], str, int]:
    payload = _json_safe_record(record)
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    body_b64 = str(payload.get("body_b64") or "")
    try:
        body_byte_size = len(base64.b64decode(body_b64.encode("ascii")))
    except Exception:
        body_byte_size = int(len(body_b64) * 0.75)
    return payload, hashlib.sha256(raw).hexdigest(), body_byte_size


def _warm_value(record: dict[str, Any], key: str) -> str | None:
    warm = record.get("warm")
    if isinstance(warm, dict):
        value = warm.get(key)
        return str(value) if value is not None else None
    return None


async def get_durable_api_response(
    cache_key: str,
) -> tuple[dict[str, Any], set[str], str | None] | None:
    """Load a durable cached HTTP response if its hard expiry is still valid."""
    if not cache_key or not durable_api_response_cache_enabled():
        return None

    stmt = (
        select(
            generated_api_responses.c.record,
            generated_api_responses.c.namespace,
            generated_api_response_tags.c.tag,
        )
        .select_from(
            generated_api_responses.outerjoin(
                generated_api_response_tags,
                generated_api_responses.c.cache_key == generated_api_response_tags.c.cache_key,
            )
        )
        .where(
            generated_api_responses.c.cache_key == cache_key,
            generated_api_responses.c.hard_expires_at > func.now(),
        )
    )

    try:
        async with async_session_factory() as session:
            result = await session.execute(stmt)
            rows = result.fetchall()
    except Exception as exc:
        logger.warning("Failed to load durable API response %s: %s", cache_key, exc)
        return None

    if not rows:
        return None

    record = rows[0]._mapping["record"]
    if not isinstance(record, dict):
        return None

    namespace = rows[0]._mapping["namespace"]
    tags: set[str] = set()
    for row in rows:
        tag = row._mapping["tag"]
        if tag is not None:
            tags.add(str(tag))
    return (_json_safe_record(record), tags, str(namespace) if namespace else None)


async def store_durable_api_response(
    cache_key: str,
    record: dict[str, Any],
    *,
    namespace: str,
    tags: Iterable[str],
) -> bool:
    """Persist a cached HTTP response so Redis can be rebuilt from Postgres."""
    if not cache_key or not namespace or not isinstance(record, dict):
        return False
    if not durable_api_response_cache_enabled():
        return False

    payload, record_hash, body_byte_size = _record_metadata(record)
    hard_expires_at = _epoch_to_datetime(payload.get("hard_exp"))
    if hard_expires_at is None:
        return False

    tag_rows = [
        {"cache_key": cache_key, "tag": tag} for tag in sorted({str(tag) for tag in tags if tag})
    ]
    values = {
        "cache_key": cache_key,
        "namespace": namespace,
        "method": _warm_value(payload, "method"),
        "path": _warm_value(payload, "path"),
        "query": _warm_value(payload, "query"),
        "record": payload,
        "status": int(payload.get("status") or 200),
        "record_hash": record_hash,
        "body_byte_size": body_byte_size,
        "soft_expires_at": _epoch_to_datetime(payload.get("soft_exp")),
        "hard_expires_at": hard_expires_at,
    }

    stmt = pg_insert(generated_api_responses).values(**values)
    stmt = stmt.on_conflict_do_update(
        index_elements=[generated_api_responses.c.cache_key],
        set_={
            "namespace": stmt.excluded.namespace,
            "method": stmt.excluded.method,
            "path": stmt.excluded.path,
            "query": stmt.excluded.query,
            "record": stmt.excluded.record,
            "status": stmt.excluded.status,
            "record_hash": stmt.excluded.record_hash,
            "body_byte_size": stmt.excluded.body_byte_size,
            "soft_expires_at": stmt.excluded.soft_expires_at,
            "hard_expires_at": stmt.excluded.hard_expires_at,
            "generated_at": func.now(),
        },
    )

    try:
        async with async_session_factory() as session:
            async with session.begin():
                await session.execute(stmt)
                await session.execute(
                    delete(generated_api_response_tags).where(
                        generated_api_response_tags.c.cache_key == cache_key
                    )
                )
                if tag_rows:
                    tag_stmt = pg_insert(generated_api_response_tags).values(tag_rows)
                    tag_stmt = tag_stmt.on_conflict_do_nothing(
                        constraint="uq_generated_api_response_tags_cache_key_tag"
                    )
                    await session.execute(tag_stmt)
        return True
    except Exception as exc:
        logger.warning("Failed to persist durable API response %s: %s", cache_key, exc)
        return False


async def delete_durable_api_response(cache_key: str) -> bool:
    if not cache_key or not durable_api_response_cache_enabled():
        return False
    try:
        async with async_session_factory() as session:
            async with session.begin():
                await session.execute(
                    delete(generated_api_responses).where(
                        generated_api_responses.c.cache_key == cache_key
                    )
                )
        return True
    except Exception as exc:
        logger.warning("Failed to delete durable API response %s: %s", cache_key, exc)
        return False


async def delete_durable_api_responses_for_tags(tags: Iterable[str]) -> int:
    tag_list = sorted({str(tag) for tag in tags if tag})
    if not tag_list or not durable_api_response_cache_enabled():
        return 0

    cache_key_stmt = select(generated_api_response_tags.c.cache_key).where(
        generated_api_response_tags.c.tag.in_(tag_list)
    )
    stmt = delete(generated_api_responses).where(
        generated_api_responses.c.cache_key.in_(cache_key_stmt)
    )

    try:
        async with async_session_factory() as session:
            async with session.begin():
                result = await session.execute(stmt)
        return int(result.rowcount or 0)
    except Exception as exc:
        logger.warning("Failed to delete durable API responses for tags %s: %s", tag_list, exc)
        return 0


async def delete_all_durable_api_responses() -> int:
    if not durable_api_response_cache_enabled():
        return 0
    try:
        async with async_session_factory() as session:
            async with session.begin():
                result = await session.execute(delete(generated_api_responses))
        return int(result.rowcount or 0)
    except Exception as exc:
        logger.warning("Failed to clear durable API responses: %s", exc)
        return 0


async def delete_expired_durable_api_responses() -> int:
    if not durable_api_response_cache_enabled():
        return 0
    try:
        async with async_session_factory() as session:
            async with session.begin():
                result = await session.execute(
                    delete(generated_api_responses).where(
                        generated_api_responses.c.hard_expires_at <= func.now()
                    )
                )
        return int(result.rowcount or 0)
    except Exception as exc:
        logger.warning("Failed to prune expired durable API responses: %s", exc)
        return 0


async def delete_durable_api_responses_with_prefix(prefix: str) -> int:
    if not durable_api_response_cache_enabled():
        return 0
    try:
        async with async_session_factory() as session:
            async with session.begin():
                result = await session.execute(
                    delete(generated_api_responses).where(
                        generated_api_responses.c.cache_key.like(f"{prefix}%")
                    )
                )
        return int(result.rowcount or 0)
    except Exception as exc:
        logger.warning("Failed to delete durable API responses with prefix %s: %s", prefix, exc)
        return 0
