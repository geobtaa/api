#!/usr/bin/env python3
"""
Prime Redis thumbnail cache entries for resources.

This script generates thumbnail cache entries directly instead of waiting for
request-time "Generating thumbnail" placeholders. It supports:
- direct image URLs
- IIIF manifests
- COG URLs
- PMTiles URLs

Progress is shown with a tqdm progress bar, including ETA.

Examples:
  python scripts/prime_thumbnail_cache.py
  python scripts/prime_thumbnail_cache.py --limit 250 --concurrency 4
  python scripts/prime_thumbnail_cache.py --force b1g_PJxxfKgpqpUT b1g_abc123
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import time
from collections import Counter
from typing import Any

import requests
from dotenv import load_dotenv
from sqlalchemy import func, select
from tqdm import tqdm

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

# Priming is allowed to wait through Redis restarts/loading instead of turning
# one transient cache outage into thousands of false per-resource failures.
os.environ.setdefault("VISUAL_ASSET_REDIS_LOADING_MAX_WAIT_SECONDS", "900")
os.environ.setdefault("VISUAL_ASSET_REDIS_LOADING_RETRY_SECONDS", "5")

from app.api.v1.utils import _get_thumbnail_asset_url, sanitize_for_json  # noqa: E402
from app.services.distribution_repository import (  # noqa: E402
    async_session_factory,
    fetch_distribution_context,
)
from app.services.image_service import ImageService  # noqa: E402
from app.services.provider_throttle import (  # noqa: E402
    provider_origin_cooldown_remaining,
    provider_request_slot,
    record_provider_failure,
    record_provider_success,
)
from app.services.thumbnail_state_service import (  # noqa: E402
    ThumbnailState,
    ThumbnailStatePayload,
    infer_source_type,
    safe_record_thumbnail_state,
)
from app.services.visual_asset_cache import (  # noqa: E402
    cache_visual_asset,
    store_durable_visual_asset,
    store_durable_visual_asset_link,
)
from app.tasks.worker import (  # noqa: E402
    _generate_cog_thumbnail_bytes,
    _generate_pmtiles_thumbnail_bytes,
    _resolve_image_url,
    _validate_image_content,
    redis_client,
)
from db.models import resource_thumbnail_state, resources  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

USER_AGENT = "BTAA-Geospatial-Data-API/1.0 (https://geo.btaa.org/)"


def _thumbnail_fetch_timeout() -> int:
    return int(os.getenv("THUMBNAIL_FETCH_TIMEOUT", "30"))


def _compute_thumbnail_image_hash(image_service: ImageService, source_url: str) -> str | None:
    """Mirror the thumbnail hash logic used by the API and worker."""
    return image_service.thumbnail_image_hash_for_source_sync(
        source_url,
        resolve_manifest=True,
    )


def _store_image_bytes(
    image_hash: str,
    image_bytes: bytes,
    content_type: str,
    *,
    resource_id: str | None = None,
) -> bool:
    """Store image bytes and MIME metadata in Redis."""
    try:
        cache_visual_asset(redis_client, f"image:{image_hash}", image_bytes)
        cache_visual_asset(redis_client, f"image_type:{image_hash}", content_type)
        store_durable_visual_asset(
            image_hash,
            asset_kind="thumbnail",
            content_type=content_type,
            body=image_bytes,
        )
        if resource_id:
            store_durable_visual_asset_link(
                resource_id,
                asset_hash=image_hash,
                asset_kind="thumbnail",
                source_signature=image_hash,
            )
        return True
    except Exception as exc:
        logger.warning("Failed to cache thumbnail %s: %s", image_hash[:12], exc)
        return False


def _set_pmtiles_skip_marker(image_hash: str) -> bool:
    """Cache the PMTiles skip marker used by the API."""
    try:
        cache_visual_asset(redis_client, f"pmtiles_skip_v2:{image_hash}", b"1")
        return True
    except Exception as exc:
        logger.warning("Failed to cache PMTiles skip marker %s: %s", image_hash[:12], exc)
        return False


def _prime_cog_thumbnail(
    source_url: str,
    image_hash: str,
    *,
    resource_id: str | None = None,
) -> bool:
    with provider_request_slot(source_url, action="thumbnail prime (COG)"):
        image_bytes = _generate_cog_thumbnail_bytes(source_url)
    if not image_bytes or len(image_bytes) < 100:
        return False
    is_valid, _ = _validate_image_content(image_bytes, "image/png")
    if not is_valid:
        return False
    return _store_image_bytes(image_hash, image_bytes, "image/png", resource_id=resource_id)


def _prime_pmtiles_thumbnail(
    source_url: str,
    image_hash: str,
    *,
    resource_id: str | None = None,
) -> tuple[bool, bool]:
    """
    Prime PMTiles thumbnail cache.

    Returns:
        (success, skip_marker_written)
    """
    with provider_request_slot(source_url, action="thumbnail prime (PMTiles)"):
        image_bytes = _generate_pmtiles_thumbnail_bytes(source_url)
    if not image_bytes or len(image_bytes) < 100:
        return (False, _set_pmtiles_skip_marker(image_hash))

    is_valid, content_type = _validate_image_content(image_bytes, None)
    if not is_valid:
        return (False, _set_pmtiles_skip_marker(image_hash))

    return (
        _store_image_bytes(
            image_hash,
            image_bytes,
            content_type or "image/png",
            resource_id=resource_id,
        ),
        False,
    )


def _prime_remote_thumbnail(
    image_hash: str,
    source_url: str,
    *,
    resource_id: str | None = None,
) -> tuple[str, str]:
    resolved_url = _resolve_image_url(source_url)
    cooldown_remaining = provider_origin_cooldown_remaining(resolved_url)
    if cooldown_remaining > 0:
        return (
            "deprioritized",
            f"provider cooldown active for {cooldown_remaining:.0f}s ({resolved_url})",
        )

    headers = {"User-Agent": USER_AGENT}
    started = time.monotonic()
    try:
        with provider_request_slot(resolved_url, action="thumbnail prime (remote)"):
            response = requests.get(
                resolved_url, timeout=_thumbnail_fetch_timeout(), headers=headers
            )
    except requests.Timeout:
        elapsed = time.monotonic() - started
        cooldown_seconds = record_provider_failure(
            resolved_url,
            elapsed_seconds=elapsed,
            failure_type="timeout",
        )
        if cooldown_seconds > 0:
            return (
                "deprioritized",
                f"provider timed out; cooling down for {cooldown_seconds:.0f}s ({resolved_url})",
            )
        return ("failed", f"request timed out after {elapsed:.1f}s ({resolved_url})")
    except requests.RequestException as exc:
        elapsed = time.monotonic() - started
        status_code = getattr(getattr(exc, "response", None), "status_code", None)
        cooldown_seconds = record_provider_failure(
            resolved_url,
            elapsed_seconds=elapsed,
            failure_type="request_error",
            status_code=status_code,
        )
        if cooldown_seconds > 0:
            return (
                "deprioritized",
                "provider request failed; "
                f"cooling down for {cooldown_seconds:.0f}s ({resolved_url})",
            )
        return ("failed", f"{exc} ({resolved_url})")

    if response.status_code in (401, 403, 418):
        logger.warning(
            "Authorization/bot-block status %s for %s", response.status_code, resolved_url
        )
        record_provider_failure(
            resolved_url,
            elapsed_seconds=time.monotonic() - started,
            failure_type=f"http_{response.status_code}",
            status_code=response.status_code,
        )
        return ("failed", f"HTTP {response.status_code} ({resolved_url})")

    try:
        response.raise_for_status()
    except requests.RequestException as exc:
        elapsed = time.monotonic() - started
        cooldown_seconds = record_provider_failure(
            resolved_url,
            elapsed_seconds=elapsed,
            failure_type="request_error",
            status_code=response.status_code,
        )
        if cooldown_seconds > 0:
            return (
                "deprioritized",
                f"provider HTTP failure; cooling down for {cooldown_seconds:.0f}s ({resolved_url})",
            )
        return ("failed", f"{exc} ({resolved_url})")

    is_valid, detected_type = _validate_image_content(
        response.content, response.headers.get("Content-Type")
    )
    if not is_valid:
        record_provider_failure(
            resolved_url,
            elapsed_seconds=time.monotonic() - started,
            failure_type="invalid_content",
            status_code=response.status_code,
        )
        return ("failed", f"invalid image content ({resolved_url})")

    if _store_image_bytes(
        image_hash,
        response.content,
        detected_type or "image/jpeg",
        resource_id=resource_id,
    ):
        record_provider_success(resolved_url)
        return ("generated", "remote")

    return ("failed", f"failed to cache thumbnail ({resolved_url})")


async def _count_resources(resource_ids: list[str]) -> int:
    async with async_session_factory() as session:
        if resource_ids:
            stmt = (
                select(func.count()).select_from(resources).where(resources.c.id.in_(resource_ids))
            )
        else:
            stmt = select(func.count()).select_from(resources)
        result = await session.execute(stmt)
        return int(result.scalar_one() or 0)


async def _fetch_resources_by_ids(resource_ids: list[str]) -> list[dict[str, Any]]:
    if not resource_ids:
        return []

    async with async_session_factory() as session:
        stmt = select(resources).where(resources.c.id.in_(resource_ids)).order_by(resources.c.id)
        result = await session.execute(stmt)
        return [sanitize_for_json(dict(row._mapping)) for row in result.fetchall()]


async def _fetch_resource_batch(last_id: str | None, batch_size: int) -> list[dict[str, Any]]:
    async with async_session_factory() as session:
        stmt = select(resources).order_by(resources.c.id).limit(batch_size)
        if last_id is not None:
            stmt = stmt.where(resources.c.id > last_id)
        result = await session.execute(stmt)
        return [sanitize_for_json(dict(row._mapping)) for row in result.fetchall()]


async def _fetch_thumbnail_states(resource_ids: list[str]) -> dict[str, dict[str, Any]]:
    if not resource_ids:
        return {}

    async with async_session_factory() as session:
        stmt = select(resource_thumbnail_state).where(
            resource_thumbnail_state.c.resource_id.in_(resource_ids)
        )
        result = await session.execute(stmt)
        rows = result.fetchall()
        return {
            str(row._mapping["resource_id"]): sanitize_for_json(dict(row._mapping)) for row in rows
        }


def _should_resume_skip(
    existing_state: dict[str, Any] | None,
    *,
    force: bool,
    retry_failures: bool,
    retry_placeheld: bool,
) -> tuple[bool, str]:
    if force or not existing_state:
        return (False, "")

    state = str(existing_state.get("state") or "").strip().lower()
    if state == ThumbnailState.SUCCESS:
        # Re-check successful records so a Redis reset can rehydrate from
        # durable visual storage instead of needlessly re-fetching upstream.
        return (False, "")
    if state == ThumbnailState.FAILURE and not retry_failures:
        return (True, "already failed in prior run")
    if state == ThumbnailState.PLACEHELD and not retry_placeheld:
        return (True, "already resolved to placeholder in prior run")
    return (False, "")


async def _prime_thumbnail_for_resource(
    resource_dict: dict[str, Any],
    *,
    force: bool,
    retry_failures: bool = False,
    retry_placeheld: bool = False,
    existing_state: dict[str, Any] | None = None,
) -> tuple[str, str, str]:
    resource_id = str(resource_dict["id"])

    should_skip, skip_reason = _should_resume_skip(
        existing_state,
        force=force,
        retry_failures=retry_failures,
        retry_placeheld=retry_placeheld,
    )
    if should_skip:
        return ("skipped-resume", resource_id, skip_reason)

    if resource_dict.get("dct_accessrights_s") == "Restricted":
        return ("skipped-restricted", resource_id, "restricted")

    distribution_context = await fetch_distribution_context(resource_id)
    image_service = ImageService(resource_dict, distribution_context=distribution_context)
    source_url = image_service.resolve_thumbnail_source_url(
        thumbnail_asset_url=await _get_thumbnail_asset_url(resource_id)
    )

    if not source_url:
        await safe_record_thumbnail_state(
            ThumbnailStatePayload(
                resource_id=resource_id,
                state=ThumbnailState.PLACEHELD,
                source_type=None,
                source_url=None,
                state_detail="No thumbnail source available during prime run",
            )
        )
        return ("skipped-no-source", resource_id, "no thumbnail source")

    try:
        image_hash = _compute_thumbnail_image_hash(image_service, source_url)
        if not image_hash:
            await safe_record_thumbnail_state(
                ThumbnailStatePayload(
                    resource_id=resource_id,
                    state=ThumbnailState.FAILURE,
                    source_type=infer_source_type(source_url),
                    source_url=source_url,
                    state_detail="Could not resolve thumbnail hash during prime run",
                    last_error="Could not resolve image hash",
                )
            )
            return ("failed", resource_id, "could not resolve image hash")

        if not force:
            cached_image = await image_service.get_cached_image(image_hash)
            if cached_image:
                _valid, cached_content_type = _validate_image_content(cached_image, None)
                store_durable_visual_asset(
                    image_hash,
                    asset_kind="thumbnail",
                    content_type=cached_content_type or "application/octet-stream",
                    body=cached_image,
                )
                store_durable_visual_asset_link(
                    resource_id,
                    asset_hash=image_hash,
                    asset_kind="thumbnail",
                    source_signature=image_hash,
                )
                await safe_record_thumbnail_state(
                    ThumbnailStatePayload(
                        resource_id=resource_id,
                        state=ThumbnailState.SUCCESS,
                        source_type=infer_source_type(source_url),
                        source_url=source_url,
                        source_hash=image_hash,
                        state_detail="Thumbnail already cached before prime run",
                    )
                )
                return ("cached", resource_id, "thumbnail already cached")
            if image_service._is_pmtiles_url(source_url) and image_service.is_pmtiles_skip_cached(
                image_hash
            ):
                await safe_record_thumbnail_state(
                    ThumbnailStatePayload(
                        resource_id=resource_id,
                        state=ThumbnailState.PLACEHELD,
                        source_type="pmtiles",
                        source_url=source_url,
                        source_hash=image_hash,
                        state_detail="PMTiles skip marker already cached before prime run",
                    )
                )
                return ("cached-skip", resource_id, "pmtiles skip marker already cached")

        if image_service._is_cog_url(source_url):
            ok = await asyncio.to_thread(
                _prime_cog_thumbnail,
                source_url,
                image_hash,
                resource_id=resource_id,
            )
            await safe_record_thumbnail_state(
                ThumbnailStatePayload(
                    resource_id=resource_id,
                    state=ThumbnailState.SUCCESS if ok else ThumbnailState.FAILURE,
                    source_type="cog",
                    source_url=source_url,
                    source_hash=image_hash,
                    state_detail="COG thumbnail primed" if ok else "COG thumbnail prime failed",
                    last_error=None if ok else "COG thumbnail prime failed",
                )
            )
            return ("generated", resource_id, "cog") if ok else ("failed", resource_id, "cog")

        if image_service._is_pmtiles_url(source_url):
            ok, wrote_skip = await asyncio.to_thread(
                _prime_pmtiles_thumbnail,
                source_url,
                image_hash,
                resource_id=resource_id,
            )
            if ok:
                await safe_record_thumbnail_state(
                    ThumbnailStatePayload(
                        resource_id=resource_id,
                        state=ThumbnailState.SUCCESS,
                        source_type="pmtiles",
                        source_url=source_url,
                        source_hash=image_hash,
                        state_detail="PMTiles thumbnail primed",
                    )
                )
                return ("generated", resource_id, "pmtiles")
            if wrote_skip:
                await safe_record_thumbnail_state(
                    ThumbnailStatePayload(
                        resource_id=resource_id,
                        state=ThumbnailState.PLACEHELD,
                        source_type="pmtiles",
                        source_url=source_url,
                        source_hash=image_hash,
                        state_detail="PMTiles source yielded no raster thumbnail during prime run",
                    )
                )
                return ("generated-skip", resource_id, "pmtiles skip marker")
            await safe_record_thumbnail_state(
                ThumbnailStatePayload(
                    resource_id=resource_id,
                    state=ThumbnailState.FAILURE,
                    source_type="pmtiles",
                    source_url=source_url,
                    source_hash=image_hash,
                    state_detail="PMTiles thumbnail prime failed",
                    last_error="PMTiles thumbnail prime failed",
                )
            )
            return ("failed", resource_id, "pmtiles")

        remote_status, remote_detail = await asyncio.to_thread(
            _prime_remote_thumbnail,
            image_hash,
            source_url,
            resource_id=resource_id,
        )
        if remote_status == "deprioritized":
            return ("deprioritized", resource_id, remote_detail)

        ok = remote_status == "generated"
        await safe_record_thumbnail_state(
            ThumbnailStatePayload(
                resource_id=resource_id,
                state=ThumbnailState.SUCCESS if ok else ThumbnailState.FAILURE,
                source_type=infer_source_type(source_url),
                source_url=source_url,
                source_hash=image_hash,
                state_detail="Remote thumbnail primed" if ok else "Remote thumbnail prime failed",
                last_error=None if ok else remote_detail,
            )
        )
        return (
            ("generated", resource_id, "remote") if ok else ("failed", resource_id, remote_detail)
        )
    except Exception as exc:
        await safe_record_thumbnail_state(
            ThumbnailStatePayload(
                resource_id=resource_id,
                state=ThumbnailState.FAILURE,
                source_type=infer_source_type(source_url),
                source_url=source_url,
                state_detail="Thumbnail prime run raised an exception",
                last_error=str(exc),
            )
        )
        return ("failed", resource_id, str(exc))


async def _process_batch(
    batch: list[dict[str, Any]],
    *,
    concurrency: int,
    force: bool,
    retry_failures: bool,
    retry_placeheld: bool,
    counters: Counter[str],
    progress: tqdm,
    failures: list[str],
) -> None:
    semaphore = asyncio.Semaphore(concurrency)
    state_map = await _fetch_thumbnail_states([str(resource_dict["id"]) for resource_dict in batch])

    async def _run(resource_dict: dict[str, Any]) -> tuple[str, str, str]:
        async with semaphore:
            return await _prime_thumbnail_for_resource(
                resource_dict,
                force=force,
                retry_failures=retry_failures,
                retry_placeheld=retry_placeheld,
                existing_state=state_map.get(str(resource_dict["id"])),
            )

    tasks = [asyncio.create_task(_run(resource_dict)) for resource_dict in batch]

    for future in asyncio.as_completed(tasks):
        status, resource_id, detail = await future
        counters[status] += 1
        if status == "failed":
            failures.append(f"{resource_id}: {detail}")
        progress.update(1)
        progress.set_postfix(
            generated=counters["generated"] + counters["generated-skip"],
            cached=counters["cached"] + counters["cached-skip"],
            skipped=(
                counters["skipped-no-source"]
                + counters["skipped-restricted"]
                + counters["skipped-resume"]
                + counters["deprioritized"]
            ),
            failed=counters["failed"],
        )


async def _run(args: argparse.Namespace) -> int:
    resource_ids = args.resource_ids
    total = len(resource_ids) if resource_ids else await _count_resources(resource_ids)
    if args.limit is not None:
        total = min(total, args.limit)

    if total == 0:
        logger.info("No resources matched the request.")
        return 0

    counters: Counter[str] = Counter()
    failures: list[str] = []

    progress = tqdm(
        total=total,
        desc="Priming thumbnail cache",
        unit="resource",
        dynamic_ncols=True,
    )

    try:
        if resource_ids:
            remaining = await _fetch_resources_by_ids(resource_ids)
            if args.limit is not None:
                remaining = remaining[: args.limit]
            for start in range(0, len(remaining), args.batch_size):
                batch = remaining[start : start + args.batch_size]
                await _process_batch(
                    batch,
                    concurrency=args.concurrency,
                    force=args.force,
                    retry_failures=args.retry_failures,
                    retry_placeheld=args.retry_placeheld,
                    counters=counters,
                    progress=progress,
                    failures=failures,
                )
        else:
            last_id: str | None = None
            processed = 0
            while processed < total:
                batch_size = min(args.batch_size, total - processed)
                batch = await _fetch_resource_batch(last_id, batch_size)
                if not batch:
                    break
                await _process_batch(
                    batch,
                    concurrency=args.concurrency,
                    force=args.force,
                    retry_failures=args.retry_failures,
                    retry_placeheld=args.retry_placeheld,
                    counters=counters,
                    progress=progress,
                    failures=failures,
                )
                processed += len(batch)
                last_id = str(batch[-1]["id"])
    finally:
        progress.close()

    logger.info(
        "Thumbnail priming complete: generated=%s generated_skip=%s cached=%s cached_skip=%s "
        "skipped_no_source=%s skipped_restricted=%s skipped_resume=%s deprioritized=%s failed=%s",
        counters["generated"],
        counters["generated-skip"],
        counters["cached"],
        counters["cached-skip"],
        counters["skipped-no-source"],
        counters["skipped-restricted"],
        counters["skipped-resume"],
        counters["deprioritized"],
        counters["failed"],
    )

    if failures:
        logger.warning("Sample failures (showing up to 20):")
        for failure in failures[:20]:
            logger.warning("  %s", failure)

    if counters["failed"] and args.strict_failures:
        return 1
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prime thumbnail cache entries.")
    parser.add_argument("resource_ids", nargs="*", help="Optional explicit resource IDs to prime")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of resources")
    parser.add_argument(
        "--batch-size", type=int, default=100, help="Database batch size for resource fetches"
    )
    parser.add_argument(
        "--concurrency", type=int, default=4, help="Concurrent thumbnail generation tasks"
    )
    parser.add_argument(
        "--force", action="store_true", help="Regenerate thumbnails even if cache exists"
    )
    parser.add_argument(
        "--retry-failures",
        action="store_true",
        help="Retry resources already marked as failure in resource_thumbnail_state",
    )
    parser.add_argument(
        "--retry-placeheld",
        action="store_true",
        help="Retry resources already marked as placeheld in resource_thumbnail_state",
    )
    parser.add_argument(
        "--strict-failures",
        action="store_true",
        help="Exit nonzero when any thumbnail fails; default logs failures and continues",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    raise SystemExit(asyncio.run(_run(args)))


if __name__ == "__main__":
    main()
