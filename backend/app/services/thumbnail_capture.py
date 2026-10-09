"""One capture, publication and restoration path for workers and bulk priming."""

from __future__ import annotations

import hashlib
import logging
import os
from dataclasses import dataclass

import requests
from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.services.provider_throttle import (
    provider_origin_cooldown_remaining,
    provider_request_slot,
    record_provider_failure,
    record_provider_success,
)
from app.services.thumbnail_policy import (
    normalize_thumbnail_image,
    source_signature,
    valid_thumbnail,
)
from app.services.visual_asset_cache import (
    app_sync_engine,
    cache_visual_asset,
    durable_visual_asset_enabled,
    get_durable_visual_asset,
    get_durable_visual_asset_hash_for_resource,
)
from db.models import generated_visual_asset_links, generated_visual_assets

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CaptureResult:
    status: str
    image_hash: str | None = None
    detail: str = ""


def _mapping_key(resource_id: str, source_url: str) -> str:
    return f"thumbnail_source:{resource_id}:{source_signature(source_url)}"


def _warm_cache(cache, image_hash: str, body: bytes, mime: str) -> None:
    if not cache_visual_asset(cache, f"image:{image_hash}", body):
        raise RuntimeError("Thumbnail cache write failed")
    if not cache_visual_asset(cache, f"image_type:{image_hash}", mime):
        raise RuntimeError("Thumbnail MIME cache write failed")


def find_thumbnail(
    resource_id: str | None, source_url: str, *, cache, require_durable: bool = False
) -> str | None:
    """Restore a validated current rendition without consulting its provider."""
    if not resource_id or not source_url:
        return None
    key = _mapping_key(resource_id, source_url)
    image_hash = None
    try:
        image_hash = cache.get(key)
        if isinstance(image_hash, bytes):
            image_hash = image_hash.decode("ascii")
        if isinstance(image_hash, str):
            body = cache.get(f"image:{image_hash}")
            if not require_durable and valid_thumbnail(body, image_hash):
                return image_hash
    except Exception as exc:
        logger.debug("Thumbnail cache unavailable: %s", exc)

    # Redis is disposable. The committed source mapping is authoritative.
    image_hash = get_durable_visual_asset_hash_for_resource(
        resource_id, asset_kind="thumbnail", source_signature=source_signature(source_url)
    )
    if not image_hash:
        return None
    durable = get_durable_visual_asset(image_hash)
    if not durable or not valid_thumbnail(durable[0], image_hash):
        logger.warning("Stored thumbnail is invalid for resource %s", resource_id)
        return None
    try:
        _warm_cache(cache, image_hash, *durable)
        cache_visual_asset(cache, key, image_hash)
    except Exception as exc:
        logger.debug("Could not warm thumbnail cache: %s", exc)
    return image_hash


def invalidate_thumbnail(resource_id: str, source_url: str, *, cache) -> bool:
    """Forget one source mapping without deleting any immutable image bytes."""
    removed = 0
    if durable_visual_asset_enabled():
        with app_sync_engine.begin() as conn:
            result = conn.execute(
                delete(generated_visual_asset_links).where(
                    generated_visual_asset_links.c.resource_id == resource_id,
                    generated_visual_asset_links.c.asset_kind == "thumbnail",
                    generated_visual_asset_links.c.source_signature == source_signature(source_url),
                )
            )
            removed = result.rowcount
    removed += cache.delete(_mapping_key(resource_id, source_url))
    return bool(removed)


def _persist_thumbnail(resource_id, signature, image_hash, body, mime):
    # Both rows commit together. An error propagates to the caller, so a
    # rebuild cannot claim success for an image that exists only in Redis.
    with app_sync_engine.begin() as conn:
        insert = pg_insert(generated_visual_assets).values(
            asset_hash=image_hash,
            asset_kind="thumbnail",
            content_type=mime,
            body=body,
            byte_size=len(body),
        )
        # The hash is computed from these exact bytes. Rewriting this row
        # only repairs corrupt storage; a different image has a different key.
        conn.execute(
            insert.on_conflict_do_update(
                index_elements=[generated_visual_assets.c.asset_hash],
                set_={"body": body, "byte_size": len(body), "content_type": mime},
            )
        )
        if resource_id:
            link = pg_insert(generated_visual_asset_links).values(
                resource_id=resource_id,
                asset_kind="thumbnail",
                source_signature=signature,
                asset_hash=image_hash,
            )
            conn.execute(
                link.on_conflict_do_update(
                    constraint="uq_generated_visual_asset_links_resource_kind_signature",
                    set_={"asset_hash": image_hash},
                )
            )


def publish_thumbnail(
    source_url: str, resource_id: str | None, body: bytes, mime: str | None, *, cache
) -> str:
    """Commit bounded image bytes and their source mapping before announcing success."""
    body, mime = normalize_thumbnail_image(body, mime)
    if not body or not mime:
        raise ValueError("Thumbnail normalization failed")
    image_hash = hashlib.sha256(body).hexdigest()
    if not valid_thumbnail(body, image_hash):
        raise ValueError("Thumbnail violates output policy")
    signature = source_signature(source_url)

    if durable_visual_asset_enabled():
        _persist_thumbnail(resource_id, signature, image_hash, body, mime)
    try:
        _warm_cache(cache, image_hash, body, mime)
        if resource_id:
            if not cache_visual_asset(cache, _mapping_key(resource_id, source_url), image_hash):
                raise RuntimeError("Thumbnail cache mapping was not stored")
    except Exception:
        if not durable_visual_asset_enabled():
            raise
        logger.warning("Thumbnail committed; Redis warming will be retried on read")
    return image_hash


def capture_thumbnail(
    source_url: str, resource_id: str | None, *, cache, force: bool = False
) -> CaptureResult:
    """Resolve, generate and publish a thumbnail; force refresh never overwrites a URL."""
    from app.services.image_service import ImageService
    from app.tasks.worker import (
        _generate_cog_thumbnail_bytes,
        _generate_pmtiles_thumbnail_bytes,
        _resolve_image_url,
    )

    if not force:
        current = find_thumbnail(
            resource_id, source_url, cache=cache, require_durable=durable_visual_asset_enabled()
        )
        if current:
            return CaptureResult("cached", current, "Validated current thumbnail")

    service = ImageService({})
    # Explicit refresh fetches a fresh manifest even when its old JSON is cached.
    if force and service._is_manifest_url(source_url):
        try:
            service.cache.delete(f"manifest:{source_url}")
        except Exception:
            pass
    if provider_origin_cooldown_remaining(source_url) > 0:
        return CaptureResult("deferred", detail="Provider cooldown; retry required")
    if service._is_manifest_url(source_url):
        with provider_request_slot(source_url, action="thumbnail manifest resolution"):
            resolved_url = _resolve_image_url(source_url)
        if resolved_url == source_url:
            raise ValueError("Manifest did not resolve to an image")
    else:
        resolved_url = _resolve_image_url(source_url)
    if provider_origin_cooldown_remaining(resolved_url) > 0:
        return CaptureResult("deferred", detail="Provider cooldown; retry required")
    mime = None
    try:
        with provider_request_slot(resolved_url, action="thumbnail capture"):
            if service._is_cog_url(source_url):
                body = _generate_cog_thumbnail_bytes(source_url)
            elif service._is_pmtiles_url(source_url):
                body = _generate_pmtiles_thumbnail_bytes(source_url)
            else:
                response = requests.get(
                    resolved_url,
                    timeout=int(os.getenv("THUMBNAIL_FETCH_TIMEOUT", "30")),
                    headers={"User-Agent": "BTAA-Geospatial-Data-API/1.0 (https://geo.btaa.org/)"},
                )
                response.raise_for_status()
                body = response.content
                mime = response.headers.get("Content-Type")
        if not body:
            raise ValueError("Provider returned no thumbnail image")
    except Exception as exc:
        record_provider_failure(
            resolved_url,
            elapsed_seconds=0,
            failure_type="capture_error",
            status_code=getattr(getattr(exc, "response", None), "status_code", None),
        )
        raise
    # Storage failures must not put a healthy provider into cooldown.
    image_hash = publish_thumbnail(source_url, resource_id, body, mime, cache=cache)
    record_provider_success(resolved_url)
    return CaptureResult("generated", image_hash, "Thumbnail durably published")
