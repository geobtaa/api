#!/usr/bin/env python3
"""
Prime shared JSON:API resource representation cache entries.

This warms the full resource object used by both:
- /api/v1/resources/{id}
- /api/v1/search plural results

Examples:
  python scripts/prime_resource_representation_cache.py
  python scripts/prime_resource_representation_cache.py --limit 500 --concurrency 4
  python scripts/prime_resource_representation_cache.py --force b1g_abc123 b1g_def456
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

from app.api.v1.utils import process_resource, sanitize_for_json  # noqa: E402
from app.services.cache_service import ENDPOINT_CACHE  # noqa: E402
from app.services.distribution_repository import async_session_factory  # noqa: E402
from app.services.resource_representation_cache import (  # noqa: E402
    get_cached_resource_representations,
    store_resource_representation,
)
from db.database import database  # noqa: E402
from db.models import resources  # noqa: E402

logger = logging.getLogger(__name__)


def configure_logging(*, verbose: bool = False) -> None:
    """Keep bulk priming output readable unless verbose diagnostics are requested."""
    level = logging.INFO if verbose else logging.WARNING
    logging.basicConfig(level=level, format="%(levelname)s: %(message)s", force=True)
    for handler in logging.getLogger().handlers:
        handler.setLevel(level)


async def _count_resources(resource_ids: list[str], limit: int | None) -> int:
    if resource_ids:
        return len(resource_ids[:limit] if limit else resource_ids)

    async with async_session_factory() as session:
        stmt = select(func.count()).select_from(resources)
        result = await session.execute(stmt)
        total = int(result.scalar_one() or 0)
        return min(total, limit) if limit else total


async def _connect_legacy_database() -> bool:
    """Connect the shared `databases` pool once before concurrent workers start."""
    if database.is_connected:
        return False

    await database.connect()
    return True


async def _disconnect_legacy_database(opened: bool) -> None:
    if opened and database.is_connected:
        await database.disconnect()


async def _fetch_resources_by_ids(
    resource_ids: list[str], limit: int | None
) -> list[dict[str, Any]]:
    if not resource_ids:
        return []

    ids = resource_ids[:limit] if limit else resource_ids
    async with async_session_factory() as session:
        stmt = select(resources).where(resources.c.id.in_(ids)).order_by(resources.c.id)
        result = await session.execute(stmt)
        return [sanitize_for_json(dict(row._mapping)) for row in result.fetchall()]


async def _fetch_resource_batch(
    last_id: str | None, batch_size: int, remaining: int | None
) -> list[dict[str, Any]]:
    limit = min(batch_size, remaining) if remaining is not None else batch_size
    if limit <= 0:
        return []

    async with async_session_factory() as session:
        stmt = select(resources).order_by(resources.c.id).limit(limit)
        if last_id is not None:
            stmt = stmt.where(resources.c.id > last_id)
        result = await session.execute(stmt)
        return [sanitize_for_json(dict(row._mapping)) for row in result.fetchall()]


async def _prime_resource_representation(resource_dict: dict[str, Any]) -> tuple[str, str]:
    resource_id = str(resource_dict.get("id") or "")
    if not resource_id:
        return ("failed", "missing resource id")

    try:
        async with async_session_factory() as session:
            resource = await process_resource(
                resource_dict,
                session,
                include_similar_items=False,
            )
        await store_resource_representation(resource_id, resource)
        return ("primed", resource_id)
    except Exception as exc:
        logger.warning("Failed to prime resource representation %s: %s", resource_id, exc)
        return ("failed", resource_id)


async def _prime_batch(
    batch: list[dict[str, Any]],
    *,
    force: bool,
    concurrency: int,
    progress: tqdm,
) -> Counter:
    counters: Counter = Counter()
    if not batch:
        return counters

    cached_ids: set[str] = set()
    if not force:
        cached = await get_cached_resource_representations(
            [str(resource.get("id") or "") for resource in batch]
        )
        cached_ids = set(cached)

    to_prime = []
    for resource in batch:
        resource_id = str(resource.get("id") or "")
        if resource_id in cached_ids:
            counters["cached"] += 1
            progress.update(1)
            continue
        to_prime.append(resource)

    semaphore = asyncio.Semaphore(max(1, concurrency))

    async def run_one(resource: dict[str, Any]) -> tuple[str, str]:
        async with semaphore:
            return await _prime_resource_representation(resource)

    tasks = [asyncio.create_task(run_one(resource)) for resource in to_prime]
    for task in asyncio.as_completed(tasks):
        status, _resource_id = await task
        counters[status] += 1
        progress.update(1)

    return counters


async def prime_resource_representation_cache(
    *,
    resource_ids: list[str],
    limit: int | None,
    batch_size: int,
    concurrency: int,
    force: bool,
) -> Counter:
    if not ENDPOINT_CACHE:
        logger.warning("ENDPOINT_CACHE is false; cache writes will be skipped.")

    opened_legacy_database = await _connect_legacy_database()
    try:
        total = await _count_resources(resource_ids, limit)
        counters: Counter = Counter()

        with tqdm(
            total=total, desc="Priming resource representations", unit="resource"
        ) as progress:
            if resource_ids:
                batch = await _fetch_resources_by_ids(resource_ids, limit)
                counters.update(
                    await _prime_batch(
                        batch,
                        force=force,
                        concurrency=concurrency,
                        progress=progress,
                    )
                )
                missing = total - len(batch)
                if missing > 0:
                    counters["missing"] += missing
                    progress.update(missing)
                return counters

            last_id = None
            remaining = limit
            while True:
                batch = await _fetch_resource_batch(last_id, batch_size, remaining)
                if not batch:
                    break

                counters.update(
                    await _prime_batch(
                        batch,
                        force=force,
                        concurrency=concurrency,
                        progress=progress,
                    )
                )
                last_id = str(batch[-1]["id"])
                if remaining is not None:
                    remaining -= len(batch)
                    if remaining <= 0:
                        break

        return counters
    finally:
        await _disconnect_legacy_database(opened_legacy_database)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prime resource representation cache entries.")
    parser.add_argument("resource_ids", nargs="*", help="Optional explicit resource IDs to prime")
    parser.add_argument("--limit", type=int, help="Maximum number of resources to prime")
    parser.add_argument("--batch-size", type=int, default=100, help="Database batch size")
    parser.add_argument("--concurrency", type=int, default=4, help="Concurrent resource builders")
    parser.add_argument("--force", action="store_true", help="Rebuild even if cache entry exists")
    parser.add_argument("--verbose", action="store_true", help="Show INFO logs from app services")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    configure_logging(verbose=args.verbose)
    counters = asyncio.run(
        prime_resource_representation_cache(
            resource_ids=args.resource_ids,
            limit=args.limit,
            batch_size=max(1, args.batch_size),
            concurrency=max(1, args.concurrency),
            force=args.force,
        )
    )
    print(
        "Resource representation priming complete: "
        f"primed={counters['primed']} "
        f"cached={counters['cached']} "
        f"missing={counters['missing']} "
        f"failed={counters['failed']}"
    )
    return 1 if counters["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
