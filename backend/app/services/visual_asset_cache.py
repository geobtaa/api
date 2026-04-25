import logging
import os
from typing import Any

from sqlalchemy import create_engine, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from db.config import DATABASE_URL
from db.models import generated_visual_assets

_engine = None
logger = logging.getLogger(__name__)


def visual_asset_ttl_seconds() -> int:
    """TTL for generated thumbnail/static-map bytes.

    A value <= 0 stores visual assets without Redis expiry. These assets are
    content-addressed or source-signature addressed, so routine TTL eviction is
    counterproductive once the priming tasks have made them hot.
    """
    return int(os.getenv("VISUAL_ASSET_CACHE_TTL_SECONDS", "0"))


def cache_visual_asset(cache: Any, key: str, value: bytes | str) -> bool:
    ttl = visual_asset_ttl_seconds()
    if ttl > 0:
        return bool(cache.setex(key, ttl, value))
    return bool(cache.set(key, value))


def durable_visual_asset_enabled() -> bool:
    return os.getenv("VISUAL_ASSET_DURABLE_STORE", "database").lower() == "database"


def _sync_engine():
    global _engine
    if _engine is None:
        sync_url = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
        _engine = create_engine(sync_url, pool_pre_ping=True)
    return _engine


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
