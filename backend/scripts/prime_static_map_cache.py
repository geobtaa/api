#!/usr/bin/env python3
"""
Prime static-map and basemap Redis cache entries for resources.

This script warms both:
- the regular static-map cache used by `/resources/{id}/static-map`
- the basemap-only cache used by thumbnail fallbacks

Progress is shown with a tqdm progress bar, including ETA.

Examples:
  python scripts/prime_static_map_cache.py
  python scripts/prime_static_map_cache.py --limit 250 --concurrency 2
  python scripts/prime_static_map_cache.py --force b1g_PJxxfKgpqpUT b1g_abc123
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from collections import Counter
from typing import Any

from dotenv import load_dotenv
from sqlalchemy import func, select
from tqdm import tqdm

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

from app.services.distribution_repository import async_session_factory  # noqa: E402
from app.services.static_map_service import StaticMapService  # noqa: E402
from db.models import resources  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


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
        stmt = (
            select(resources.c.id, resources.c.locn_geometry, resources.c.dcat_bbox)
            .where(resources.c.id.in_(resource_ids))
            .order_by(resources.c.id)
        )
        result = await session.execute(stmt)
        return [dict(row._mapping) for row in result.fetchall()]


async def _fetch_resource_batch(last_id: str | None, batch_size: int) -> list[dict[str, Any]]:
    async with async_session_factory() as session:
        stmt = (
            select(resources.c.id, resources.c.locn_geometry, resources.c.dcat_bbox)
            .order_by(resources.c.id)
            .limit(batch_size)
        )
        if last_id is not None:
            stmt = stmt.where(resources.c.id > last_id)
        result = await session.execute(stmt)
        return [dict(row._mapping) for row in result.fetchall()]


def _prime_static_maps_sync(resource_id: str, geometry: Any, force: bool) -> tuple[str, str]:
    service = StaticMapService()
    source_signature = service.geometry_signature(geometry)
    static_map_variant = service.geometry_variant()
    basemap_variant = service.basemap_variant()

    if force:
        needs_static_map = True
        needs_basemap = True
    else:
        needs_static_map = not service.materialize_cached_variant_sync(
            resource_id,
            variant=static_map_variant,
            source_signature=source_signature,
        )
        needs_basemap = not service.materialize_cached_variant_sync(
            resource_id,
            variant=basemap_variant,
            source_signature=source_signature,
        )

    if not needs_static_map and not needs_basemap:
        return ("cached", "both caches already primed")

    generated = 0
    failed = 0

    if geometry:
        if needs_static_map:
            if service.generate_map(
                resource_id,
                geometry,
                source_signature=source_signature,
            ):
                generated += 1
            else:
                failed += 1
        if needs_basemap:
            if service.generate_basemap(
                resource_id,
                geometry,
                source_signature=source_signature,
            ):
                generated += 1
            else:
                failed += 1
    else:
        if needs_static_map:
            if service.generate_global_map(resource_id, source_signature=source_signature):
                generated += 1
            else:
                failed += 1
        if needs_basemap:
            if service.generate_global_basemap(resource_id, source_signature=source_signature):
                generated += 1
            else:
                failed += 1

    if failed and generated:
        return ("partial", f"generated={generated} failed={failed}")
    if failed:
        return ("failed", f"generated={generated} failed={failed}")
    return ("generated", f"generated={generated}")


async def _prime_static_maps_for_resource(
    resource_dict: dict[str, Any], *, force: bool
) -> tuple[str, str, str]:
    resource_id = str(resource_dict["id"])
    geometry = resource_dict.get("locn_geometry") or resource_dict.get("dcat_bbox")

    try:
        status, detail = await asyncio.to_thread(
            _prime_static_maps_sync, resource_id, geometry, force
        )
        return (status, resource_id, detail)
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
            return await _prime_static_maps_for_resource(resource_dict, force=force)

    tasks = [asyncio.create_task(_run(resource_dict)) for resource_dict in batch]

    for future in asyncio.as_completed(tasks):
        status, resource_id, detail = await future
        counters[status] += 1
        if status in {"failed", "partial"}:
            failures.append(f"{resource_id}: {detail}")
        progress.update(1)
        progress.set_postfix(
            generated=counters["generated"],
            cached=counters["cached"],
            partial=counters["partial"],
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
        desc="Priming static-map caches",
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
        "Static-map priming complete: generated=%s cached=%s partial=%s failed=%s",
        counters["generated"],
        counters["cached"],
        counters["partial"],
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
    parser = argparse.ArgumentParser(description="Prime static-map and basemap cache entries.")
    parser.add_argument("resource_ids", nargs="*", help="Optional explicit resource IDs to prime")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of resources")
    parser.add_argument(
        "--batch-size", type=int, default=100, help="Database batch size for resource fetches"
    )
    parser.add_argument(
        "--concurrency", type=int, default=2, help="Concurrent static-map generation tasks"
    )
    parser.add_argument("--force", action="store_true", help="Regenerate maps even if cache exists")
    parser.add_argument(
        "--strict-failures",
        action="store_true",
        help="Exit nonzero when any static map fails; default logs failures and continues",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    raise SystemExit(asyncio.run(_run(args)))


if __name__ == "__main__":
    main()
