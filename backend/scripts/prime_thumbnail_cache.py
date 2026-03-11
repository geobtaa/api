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
import hashlib
import json
import logging
import os
import sys
from collections import Counter
from typing import Any

import requests
from dotenv import load_dotenv
from sqlalchemy import func, select
from tqdm import tqdm

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

from app.api.v1.utils import sanitize_for_json  # noqa: E402
from app.services.distribution_repository import (  # noqa: E402
    async_session_factory,
    fetch_distribution_context,
)
from app.services.image_service import ImageService  # noqa: E402
from app.tasks.worker import (  # noqa: E402
    _cog_thumbnail_image_hash,
    _generate_cog_thumbnail_bytes,
    _generate_pmtiles_thumbnail_bytes,
    _pmtiles_thumbnail_image_hash,
    _resolve_image_url,
    _validate_image_content,
    redis_client,
)
from db.models import resources  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

USER_AGENT = "BTAA-Geospatial-Data-API/1.0 (https://geo.btaa.org/)"


def _thumbnail_fetch_timeout() -> int:
    return int(os.getenv("THUMBNAIL_FETCH_TIMEOUT", "30"))


def _cache_ttl() -> int:
    return int(os.getenv("REDIS_TTL", 604800))


def _compute_thumbnail_image_hash(image_service: ImageService, source_url: str) -> str | None:
    """Mirror the thumbnail hash logic used by the API and worker."""
    if image_service._is_cog_url(source_url):
        return _cog_thumbnail_image_hash(source_url)
    if image_service._is_pmtiles_url(source_url):
        return _pmtiles_thumbnail_image_hash(source_url)
    if image_service._is_manifest_url(source_url):
        manifest_cache_key = f"manifest:{source_url}"
        try:
            cached = image_service.cache.get(manifest_cache_key)
            if cached:
                manifest_json = json.loads(cached)
                resolved = image_service._extract_thumbnail_from_manifest_json(
                    manifest_json, source_url
                )
                if resolved:
                    resolved = image_service._standardize_iiif_url(resolved)
                    return hashlib.sha256(resolved.encode()).hexdigest()
        except Exception as exc:
            logger.debug("Manifest cache read failed for %s: %s", source_url, exc)

        resolved_url = _resolve_image_url(source_url)
        if resolved_url != source_url:
            return hashlib.sha256(resolved_url.encode()).hexdigest()
        return None

    standardized = image_service._standardize_iiif_url(source_url)
    return hashlib.sha256(standardized.encode()).hexdigest()


def _store_image_bytes(image_hash: str, image_bytes: bytes, content_type: str) -> bool:
    """Store image bytes and MIME metadata in Redis."""
    try:
        ttl = _cache_ttl()
        redis_client.setex(f"image:{image_hash}", ttl, image_bytes)
        redis_client.setex(f"image_type:{image_hash}", ttl, content_type)
        return True
    except Exception as exc:
        logger.warning("Failed to cache thumbnail %s: %s", image_hash[:12], exc)
        return False


def _set_pmtiles_skip_marker(image_hash: str) -> bool:
    """Cache the PMTiles skip marker used by the API."""
    try:
        redis_client.setex(f"pmtiles_skip_v2:{image_hash}", _cache_ttl(), b"1")
        return True
    except Exception as exc:
        logger.warning("Failed to cache PMTiles skip marker %s: %s", image_hash[:12], exc)
        return False


def _prime_cog_thumbnail(source_url: str, image_hash: str) -> bool:
    image_bytes = _generate_cog_thumbnail_bytes(source_url)
    if not image_bytes or len(image_bytes) < 100:
        return False
    is_valid, _ = _validate_image_content(image_bytes, "image/png")
    if not is_valid:
        return False
    return _store_image_bytes(image_hash, image_bytes, "image/png")


def _prime_pmtiles_thumbnail(source_url: str, image_hash: str) -> tuple[bool, bool]:
    """
    Prime PMTiles thumbnail cache.

    Returns:
        (success, skip_marker_written)
    """
    image_bytes = _generate_pmtiles_thumbnail_bytes(source_url)
    if not image_bytes or len(image_bytes) < 100:
        return (False, _set_pmtiles_skip_marker(image_hash))

    is_valid, content_type = _validate_image_content(image_bytes, None)
    if not is_valid:
        return (False, _set_pmtiles_skip_marker(image_hash))

    return (_store_image_bytes(image_hash, image_bytes, content_type or "image/png"), False)


def _prime_remote_thumbnail(image_hash: str, source_url: str) -> bool:
    resolved_url = _resolve_image_url(source_url)
    headers = {"User-Agent": USER_AGENT}
    response = requests.get(resolved_url, timeout=_thumbnail_fetch_timeout(), headers=headers)

    if response.status_code in (401, 403, 418):
        logger.warning(
            "Authorization/bot-block status %s for %s", response.status_code, resolved_url
        )
        return False

    response.raise_for_status()

    is_valid, detected_type = _validate_image_content(
        response.content, response.headers.get("Content-Type")
    )
    if not is_valid:
        return False

    return _store_image_bytes(image_hash, response.content, detected_type or "image/jpeg")


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


async def _prime_thumbnail_for_resource(
    resource_dict: dict[str, Any], *, force: bool
) -> tuple[str, str, str]:
    resource_id = str(resource_dict["id"])

    if resource_dict.get("dct_accessrights_s") == "Restricted":
        return ("skipped-restricted", resource_id, "restricted")

    distribution_context = await fetch_distribution_context(resource_id)
    image_service = ImageService(resource_dict, distribution_context=distribution_context)
    source_url = image_service._get_thumbnail_source_url()

    if not source_url:
        return ("skipped-no-source", resource_id, "no thumbnail source")

    try:
        image_hash = _compute_thumbnail_image_hash(image_service, source_url)
        if not image_hash:
            return ("failed", resource_id, "could not resolve image hash")

        if not force:
            cached_image = await image_service.get_cached_image(image_hash)
            if cached_image:
                return ("cached", resource_id, "thumbnail already cached")
            if image_service._is_pmtiles_url(source_url) and image_service.is_pmtiles_skip_cached(
                image_hash
            ):
                return ("cached-skip", resource_id, "pmtiles skip marker already cached")

        if image_service._is_cog_url(source_url):
            ok = await asyncio.to_thread(_prime_cog_thumbnail, source_url, image_hash)
            return ("generated", resource_id, "cog") if ok else ("failed", resource_id, "cog")

        if image_service._is_pmtiles_url(source_url):
            ok, wrote_skip = await asyncio.to_thread(
                _prime_pmtiles_thumbnail, source_url, image_hash
            )
            if ok:
                return ("generated", resource_id, "pmtiles")
            if wrote_skip:
                return ("generated-skip", resource_id, "pmtiles skip marker")
            return ("failed", resource_id, "pmtiles")

        ok = await asyncio.to_thread(_prime_remote_thumbnail, image_hash, source_url)
        return ("generated", resource_id, "remote") if ok else ("failed", resource_id, "remote")
    except Exception as exc:
        return ("failed", resource_id, str(exc))


async def _process_batch(
    batch: list[dict[str, Any]],
    *,
    concurrency: int,
    force: bool,
    counters: Counter[str],
    progress: tqdm,
    failures: list[str],
) -> None:
    semaphore = asyncio.Semaphore(concurrency)

    async def _run(resource_dict: dict[str, Any]) -> tuple[str, str, str]:
        async with semaphore:
            return await _prime_thumbnail_for_resource(resource_dict, force=force)

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
            skipped=counters["skipped-no-source"] + counters["skipped-restricted"],
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
        "skipped_no_source=%s skipped_restricted=%s failed=%s",
        counters["generated"],
        counters["generated-skip"],
        counters["cached"],
        counters["cached-skip"],
        counters["skipped-no-source"],
        counters["skipped-restricted"],
        counters["failed"],
    )

    if failures:
        logger.warning("Sample failures (showing up to 20):")
        for failure in failures[:20]:
            logger.warning("  %s", failure)

    return 1 if counters["failed"] else 0


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
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    raise SystemExit(asyncio.run(_run(args)))


if __name__ == "__main__":
    main()
