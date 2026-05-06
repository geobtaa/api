from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, Optional
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.services.distribution_repository import async_session_factory
from app.services.thumbnail_alias_service import thumbnail_alias_service
from db.config import DATABASE_URL
from db.models import resource_thumbnail_state
from db.sync_engine import create_app_sync_engine

logger = logging.getLogger(__name__)

ThumbnailStateValue = Literal["queued", "success", "failure", "placeheld"]


class ThumbnailState:
    QUEUED = "queued"
    SUCCESS = "success"
    FAILURE = "failure"
    PLACEHELD = "placeheld"


def _sync_database_url() -> str:
    return DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")


_sync_engine = create_app_sync_engine(_sync_database_url())


def _utcnow() -> datetime:
    return datetime.utcnow()


def infer_source_type(source_url: str | None) -> str | None:
    """Infer thumbnail source type from the resolved/original URL."""
    if not source_url:
        return None
    lowered = source_url.lower()
    if lowered.endswith((".pmtiles",)) or ".pmtiles?" in lowered:
        return "pmtiles"
    if (
        lowered.endswith((".tif", ".tiff"))
        or ".tif?" in lowered
        or "geotiff" in lowered
        or "display_raster" in lowered
    ):
        return "cog"
    if (
        source_url.endswith(("/iiif3/manifest", "/iiif/manifest", "/manifest", "manifest.json"))
        or "/manifest" in source_url
        or (".json" in source_url and ("iiif" in lowered or "/object/" in lowered))
    ):
        return "manifest"
    return "remote"


def extract_source_host(source_url: str | None) -> str | None:
    if not source_url:
        return None
    parsed = urlparse(source_url)
    return parsed.netloc.lower() or None


@dataclass(frozen=True)
class ThumbnailStatePayload:
    resource_id: str
    state: ThumbnailStateValue
    source_type: str | None = None
    source_url: str | None = None
    source_hash: str | None = None
    queue_task_id: str | None = None
    state_detail: str | None = None
    last_error: str | None = None


class ThumbnailStateService:
    """Persist current thumbnail harvesting state per resource."""

    def _build_values(self, payload: ThumbnailStatePayload) -> dict[str, Any]:
        now = _utcnow()
        values: dict[str, Any] = {
            "resource_id": payload.resource_id,
            "state": payload.state,
            "source_type": payload.source_type,
            "source_url": payload.source_url,
            "source_host": extract_source_host(payload.source_url),
            "source_hash": payload.source_hash,
            "queue_task_id": payload.queue_task_id,
            "state_detail": payload.state_detail,
            "last_error": payload.last_error,
            "last_transition_at": now,
            "updated_at": now,
        }
        if payload.state == ThumbnailState.QUEUED:
            values["queued_at"] = now
        elif payload.state == ThumbnailState.SUCCESS:
            values["succeeded_at"] = now
            values["last_error"] = None
        elif payload.state == ThumbnailState.FAILURE:
            values["failed_at"] = now
        elif payload.state == ThumbnailState.PLACEHELD:
            values["placeheld_at"] = now
            values["last_error"] = None
        return values

    def _build_upsert_stmt(self, payload: ThumbnailStatePayload):
        values = self._build_values(payload)
        stmt = pg_insert(resource_thumbnail_state).values(**values)
        stmt = stmt.on_conflict_do_update(
            index_elements=[resource_thumbnail_state.c.resource_id],
            set_={
                "state": stmt.excluded.state,
                "source_type": stmt.excluded.source_type,
                "source_url": stmt.excluded.source_url,
                "source_host": stmt.excluded.source_host,
                "source_hash": stmt.excluded.source_hash,
                "queue_task_id": stmt.excluded.queue_task_id,
                "state_detail": stmt.excluded.state_detail,
                "last_error": stmt.excluded.last_error,
                "queued_at": stmt.excluded.queued_at
                if payload.state == ThumbnailState.QUEUED
                else resource_thumbnail_state.c.queued_at,
                "succeeded_at": stmt.excluded.succeeded_at
                if payload.state == ThumbnailState.SUCCESS
                else resource_thumbnail_state.c.succeeded_at,
                "failed_at": stmt.excluded.failed_at
                if payload.state == ThumbnailState.FAILURE
                else resource_thumbnail_state.c.failed_at,
                "placeheld_at": stmt.excluded.placeheld_at
                if payload.state == ThumbnailState.PLACEHELD
                else resource_thumbnail_state.c.placeheld_at,
                "last_transition_at": stmt.excluded.last_transition_at,
                "updated_at": stmt.excluded.updated_at,
            },
        )
        return stmt

    async def _sync_alias_async(self, payload: ThumbnailStatePayload) -> None:
        """Mirror success/placeheld state into the Redis alias cache."""
        if payload.state == ThumbnailState.SUCCESS and payload.source_hash:
            await thumbnail_alias_service.set_hash(payload.resource_id, payload.source_hash)
            return
        if payload.state == ThumbnailState.PLACEHELD:
            await thumbnail_alias_service.delete(payload.resource_id)

    def _sync_alias_sync(self, payload: ThumbnailStatePayload) -> None:
        """Mirror success/placeheld state into the Redis alias cache."""
        if payload.state == ThumbnailState.SUCCESS and payload.source_hash:
            thumbnail_alias_service.set_hash_sync(payload.resource_id, payload.source_hash)
            return
        if payload.state == ThumbnailState.PLACEHELD:
            thumbnail_alias_service.delete_sync(payload.resource_id)

    async def _invalidate_success_caches_async(self, payload: ThumbnailStatePayload) -> None:
        """Evict cached API responses that embedded this resource before the thumbnail was hot."""
        if payload.state != ThumbnailState.SUCCESS or not payload.source_hash:
            return
        try:
            from app.services.cache_service import CacheService

            deleted = await CacheService().invalidate_tags([f"resource:{payload.resource_id}"])
            if deleted:
                logger.info(
                    "Invalidated %s cached response(s) for thumbnail success on %s",
                    deleted,
                    payload.resource_id,
                )
        except Exception as exc:
            logger.warning(
                "Failed to invalidate caches for thumbnail success on %s: %s",
                payload.resource_id,
                exc,
            )

    def _invalidate_success_caches_sync(self, payload: ThumbnailStatePayload) -> None:
        """Sync wrapper for thumbnail success cache invalidation."""
        if payload.state != ThumbnailState.SUCCESS or not payload.source_hash:
            return

        async def _run() -> None:
            await self._invalidate_success_caches_async(payload)

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(_run())
        else:
            loop.create_task(_run())

    async def record_state(self, payload: ThumbnailStatePayload) -> None:
        async with async_session_factory() as session:
            await session.execute(self._build_upsert_stmt(payload))
            await session.commit()
        await self._sync_alias_async(payload)
        await self._invalidate_success_caches_async(payload)

    def record_state_sync(self, payload: ThumbnailStatePayload) -> None:
        with _sync_engine.begin() as conn:
            conn.execute(self._build_upsert_stmt(payload))
        self._sync_alias_sync(payload)
        self._invalidate_success_caches_sync(payload)

    async def get_state(self, resource_id: str) -> Optional[dict[str, Any]]:
        async with async_session_factory() as session:
            result = await session.execute(
                select(resource_thumbnail_state).where(
                    resource_thumbnail_state.c.resource_id == resource_id
                )
            )
            row = result.fetchone()
            return dict(row._mapping) if row else None

    def get_state_sync(self, resource_id: str) -> Optional[dict[str, Any]]:
        with _sync_engine.begin() as conn:
            result = conn.execute(
                select(resource_thumbnail_state).where(
                    resource_thumbnail_state.c.resource_id == resource_id
                )
            )
            row = result.fetchone()
            return dict(row._mapping) if row else None


thumbnail_state_service = ThumbnailStateService()


def thumbnail_state_enabled() -> bool:
    """Allow emergency disable if migration hasn't been applied yet."""
    disabled = os.getenv("THUMBNAIL_STATE_DISABLED", "").lower()
    return disabled not in {"1", "true", "yes"}


async def safe_record_thumbnail_state(payload: ThumbnailStatePayload) -> None:
    if not thumbnail_state_enabled():
        return
    try:
        await thumbnail_state_service.record_state(payload)
    except Exception as exc:
        logger.warning("Failed to persist thumbnail state for %s: %s", payload.resource_id, exc)


def safe_record_thumbnail_state_sync(payload: ThumbnailStatePayload) -> None:
    if not thumbnail_state_enabled():
        return
    try:
        thumbnail_state_service.record_state_sync(payload)
    except Exception as exc:
        logger.warning("Failed to persist thumbnail state for %s: %s", payload.resource_id, exc)
