import logging
import os
import time
from typing import Any, Callable, TypeVar

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from db.models import generated_visual_asset_links, generated_visual_assets
from db.session import sync_engine as app_sync_engine

logger = logging.getLogger(__name__)
T = TypeVar("T")


def visual_asset_ttl_seconds() -> int:
    """TTL for generated thumbnail/static-map bytes.

    A value <= 0 stores visual assets without Redis expiry. These assets are
    content-addressed or source-signature addressed, so routine TTL eviction is
    counterproductive once the priming tasks have made them hot.
    """
    return int(os.getenv("VISUAL_ASSET_CACHE_TTL_SECONDS", "0"))


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        logger.warning("Invalid float for %s=%r; using default=%s", name, value, default)
        return default


def redis_loading_max_wait_seconds() -> float:
    """How long visual-cache operations should wait while Redis is loading."""
    return max(0.0, _env_float("VISUAL_ASSET_REDIS_LOADING_MAX_WAIT_SECONDS", 0.0))


def redis_loading_retry_seconds() -> float:
    """Retry cadence while Redis reports it is loading its persisted dataset."""
    return max(0.05, _env_float("VISUAL_ASSET_REDIS_LOADING_RETRY_SECONDS", 5.0))


def is_redis_loading_error(exc: BaseException) -> bool:
    """Return True when Redis rejected the command because it is still loading."""
    if exc.__class__.__name__ == "BusyLoadingError":
        return True
    return "redis is loading the dataset in memory" in str(exc).lower()


def redis_operation_with_loading_retry(
    operation: Callable[[], T],
    *,
    operation_name: str,
) -> T:
    """
    Run a Redis operation, optionally waiting through Redis LOADING states.

    Priming jobs set VISUAL_ASSET_REDIS_LOADING_MAX_WAIT_SECONDS so a Redis
    restart/load does not become thousands of false per-resource failures.
    Normal request handling keeps the default zero wait and falls back quickly.
    """
    deadline = time.monotonic() + redis_loading_max_wait_seconds()
    warned = False

    while True:
        try:
            return operation()
        except Exception as exc:
            if not is_redis_loading_error(exc) or time.monotonic() >= deadline:
                raise

            remaining = max(0.0, deadline - time.monotonic())
            if not warned:
                logger.warning(
                    "%s blocked while Redis loads its dataset; waiting up to %.0fs",
                    operation_name,
                    remaining,
                )
                warned = True
            time.sleep(min(redis_loading_retry_seconds(), remaining))


def cache_visual_asset(cache: Any, key: str, value: bytes | str) -> bool:
    ttl = visual_asset_ttl_seconds()
    if ttl > 0:
        return bool(
            redis_operation_with_loading_retry(
                lambda: cache.setex(key, ttl, value),
                operation_name=f"cache visual asset {key}",
            )
        )
    return bool(
        redis_operation_with_loading_retry(
            lambda: cache.set(key, value),
            operation_name=f"cache visual asset {key}",
        )
    )


def durable_visual_asset_enabled() -> bool:
    return os.getenv("VISUAL_ASSET_DURABLE_STORE", "database").lower() == "database"


def _sync_engine():
    return app_sync_engine


def store_durable_visual_asset(
    asset_hash: str,
    *,
    asset_kind: str,
    content_type: str,
    body: bytes,
) -> bool:
    if not durable_visual_asset_enabled() or not asset_hash or not body:
        return False

    values = {
        "asset_hash": asset_hash,
        "asset_kind": asset_kind,
        "content_type": content_type,
        "body": body,
        "byte_size": len(body),
    }
    stmt = pg_insert(generated_visual_assets).values(**values)
    stmt = stmt.on_conflict_do_update(
        index_elements=[generated_visual_assets.c.asset_hash],
        set_={
            "asset_kind": stmt.excluded.asset_kind,
            "content_type": stmt.excluded.content_type,
            "body": stmt.excluded.body,
            "byte_size": stmt.excluded.byte_size,
        },
    )
    try:
        with _sync_engine().begin() as conn:
            conn.execute(stmt)
        return True
    except Exception as exc:
        logger.warning("Failed to persist visual asset %s: %s", asset_hash[:12], exc)
        return False


def store_durable_visual_asset_link(
    resource_id: str,
    *,
    asset_hash: str,
    asset_kind: str,
    source_signature: str | None = None,
) -> bool:
    if not durable_visual_asset_enabled() or not resource_id or not asset_hash:
        return False

    values = {
        "resource_id": resource_id,
        "asset_hash": asset_hash,
        "asset_kind": asset_kind,
        "source_signature": source_signature or "",
    }
    stmt = pg_insert(generated_visual_asset_links).values(**values)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_generated_visual_asset_links_resource_kind_signature",
        set_={"asset_hash": stmt.excluded.asset_hash},
    )
    try:
        with _sync_engine().begin() as conn:
            conn.execute(stmt)
        return True
    except Exception as exc:
        logger.warning(
            "Failed to persist visual asset link %s %s %s: %s",
            resource_id,
            asset_kind,
            asset_hash[:12],
            exc,
        )
        return False


def get_durable_visual_asset_hash_for_resource(
    resource_id: str,
    *,
    asset_kind: str,
    source_signature: str | None = None,
) -> str | None:
    if not durable_visual_asset_enabled() or not resource_id:
        return None

    stmt = select(generated_visual_asset_links.c.asset_hash).where(
        generated_visual_asset_links.c.resource_id == resource_id,
        generated_visual_asset_links.c.asset_kind == asset_kind,
        generated_visual_asset_links.c.source_signature == (source_signature or ""),
    )
    try:
        with _sync_engine().connect() as conn:
            row = conn.execute(stmt).fetchone()
    except Exception as exc:
        logger.warning(
            "Failed to load durable visual asset link %s %s: %s",
            resource_id,
            asset_kind,
            exc,
        )
        return None
    if not row:
        return None
    return str(row._mapping["asset_hash"])


def get_durable_visual_asset(asset_hash: str) -> tuple[bytes, str] | None:
    if not durable_visual_asset_enabled() or not asset_hash:
        return None

    stmt = select(
        generated_visual_assets.c.body,
        generated_visual_assets.c.content_type,
    ).where(generated_visual_assets.c.asset_hash == asset_hash)
    try:
        with _sync_engine().connect() as conn:
            row = conn.execute(stmt).fetchone()
    except Exception as exc:
        logger.warning("Failed to load durable visual asset %s: %s", asset_hash[:12], exc)
        return None
    if not row:
        return None
    return (bytes(row._mapping["body"]), str(row._mapping["content_type"]))
