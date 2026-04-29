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
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

from dotenv import load_dotenv
from sqlalchemy import func, select
from tqdm import tqdm

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

from app.api.v1.utils import process_resource, sanitize_for_json  # noqa: E402
from app.services.cache_service import ENDPOINT_CACHE  # noqa: E402
from app.services.data_dictionary_repository import (  # noqa: E402
    fetch_resource_data_dictionaries_map,
    serialize_resource_data_dictionaries,
)
from app.services.distribution_repository import (  # noqa: E402
    DistributionContext,
    async_session_factory,
    build_distribution_context,
    fetch_distribution_context_map,
)
from app.services.resource_representation_cache import (  # noqa: E402
    get_cached_resource_representations,
    store_resource_representation,
    store_resource_representations,
)
from db.database import database  # noqa: E402
from db.models import (  # noqa: E402
    resource_allmaps,
    resource_assets,
    resource_relationships,
    resources,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ResourceBatchContext:
    distribution_contexts: dict[str, DistributionContext]
    allmaps_attributes: dict[str, dict[str, Any]]
    bridge_asset_download_rows: dict[str, list[dict[str, Any]]]
    relationships: dict[str, dict[str, list[dict[str, str]]]]
    thumbnail_asset_urls: dict[str, str | None]
    data_dictionaries: dict[str, list[dict[str, Any]]]


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


async def _fetch_allmaps_attributes_map(
    resource_ids: list[str],
) -> dict[str, dict[str, Any]]:
    ids = list(dict.fromkeys(str(resource_id) for resource_id in resource_ids if resource_id))
    if not ids:
        return {}

    try:
        async with async_session_factory() as session:
            stmt = select(resource_allmaps).where(resource_allmaps.c.resource_id.in_(ids))
            result = await session.execute(stmt)
            rows = result.fetchall()
    except Exception as exc:
        logger.warning("Failed to batch-fetch Allmaps attributes: %s", exc)
        return {}

    attributes_by_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        mapping = dict(row._mapping)
        resource_id = str(mapping.get("resource_id") or "")
        if not resource_id:
            continue

        manifest_uri = mapping.get("iiif_manifest_uri")
        annotated = mapping.get("annotated")
        attributes = {
            "allmaps_id": mapping.get("allmaps_id"),
            "allmaps_annotated": annotated,
            "allmaps_manifest_uri": manifest_uri,
        }
        if manifest_uri and annotated:
            attributes["allmaps_annotation_url"] = (
                f"https://annotations.allmaps.org/?url={quote(manifest_uri, safe='')}"
            )
        attributes_by_id[resource_id] = attributes
    return attributes_by_id


async def _fetch_relationships_map(
    resource_ids: list[str],
) -> dict[str, dict[str, list[dict[str, str]]]]:
    ids = list(dict.fromkeys(str(resource_id) for resource_id in resource_ids if resource_id))
    if not ids:
        return {}

    try:
        async with async_session_factory() as session:
            stmt = (
                select(
                    resource_relationships.c.subject_id,
                    resource_relationships.c.predicate,
                    resource_relationships.c.object_id,
                    resources.c.dct_title_s,
                )
                .select_from(
                    resource_relationships.join(
                        resources,
                        resources.c.id == resource_relationships.c.object_id,
                    )
                )
                .where(resource_relationships.c.subject_id.in_(ids))
                .order_by(resource_relationships.c.subject_id, resources.c.dct_title_s.asc())
            )
            result = await session.execute(stmt)
            rows = result.fetchall()
    except Exception as exc:
        logger.warning("Failed to batch-fetch resource relationships: %s", exc)
        return {}

    relationships_by_id: dict[str, dict[str, list[dict[str, str]]]] = {}
    for row in rows:
        mapping = row._mapping
        resource_id = str(mapping["subject_id"])
        predicate = str(mapping["predicate"])
        relationships_by_id.setdefault(resource_id, {}).setdefault(predicate, []).append(
            {
                "resource_id": mapping["object_id"],
                "resource_title": mapping["dct_title_s"],
                "link": f"/resources/{mapping['object_id']}",
            }
        )
    return relationships_by_id


async def _fetch_bridge_asset_download_rows_map(
    resource_ids: list[str],
) -> dict[str, list[dict[str, Any]]]:
    ids = list(dict.fromkeys(str(resource_id) for resource_id in resource_ids if resource_id))
    if not ids:
        return {}

    try:
        async with async_session_factory() as session:
            stmt = (
                select(
                    resource_assets.c.resource_id,
                    resource_assets.c.label,
                    resource_assets.c.title,
                    resource_assets.c.file_url,
                    resource_assets.c.file_mime_type,
                    resource_assets.c.file_size,
                    resource_assets.c.position,
                    resource_assets.c.id,
                )
                .where(
                    resource_assets.c.resource_id.in_(ids),
                    resource_assets.c.dct_references_uri_key == "download",
                    resource_assets.c.file_url.is_not(None),
                )
                .order_by(
                    resource_assets.c.resource_id,
                    resource_assets.c.position.asc(),
                    resource_assets.c.id.asc(),
                )
            )
            result = await session.execute(stmt)
            rows = result.fetchall()
    except Exception as exc:
        logger.warning("Failed to batch-fetch bridge asset downloads: %s", exc)
        return {}

    rows_by_id: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        mapping = dict(row._mapping)
        resource_id = str(mapping.pop("resource_id") or "")
        if resource_id:
            rows_by_id.setdefault(resource_id, []).append(mapping)
    return rows_by_id


async def _fetch_thumbnail_asset_url_map(resource_ids: list[str]) -> dict[str, str | None]:
    ids = list(dict.fromkeys(str(resource_id) for resource_id in resource_ids if resource_id))
    if not ids:
        return {}

    urls_by_id: dict[str, str | None] = {resource_id: None for resource_id in ids}
    try:
        async with async_session_factory() as session:
            stmt = (
                select(
                    resource_assets.c.resource_id,
                    resource_assets.c.file_url,
                    resource_assets.c.position,
                    resource_assets.c.id,
                )
                .where(
                    resource_assets.c.resource_id.in_(ids),
                    resource_assets.c.thumbnail.is_(True),
                    resource_assets.c.file_url.is_not(None),
                )
                .order_by(
                    resource_assets.c.resource_id,
                    resource_assets.c.position.asc(),
                    resource_assets.c.id.asc(),
                )
            )
            result = await session.execute(stmt)
            rows = result.fetchall()
    except Exception as exc:
        logger.warning("Failed to batch-fetch thumbnail asset URLs: %s", exc)
        return urls_by_id
    for row in rows:
        mapping = row._mapping
        resource_id = str(mapping["resource_id"])
        if urls_by_id.get(resource_id):
            continue
        raw_url = mapping["file_url"]
        urls_by_id[resource_id] = raw_url.strip() if isinstance(raw_url, str) else None
    return urls_by_id


async def _fetch_data_dictionaries_map(
    resource_ids: list[str],
) -> dict[str, list[dict[str, Any]]]:
    ids = list(dict.fromkeys(str(resource_id) for resource_id in resource_ids if resource_id))
    if not ids:
        return {}

    try:
        async with async_session_factory() as session:
            dictionaries_by_id = await fetch_resource_data_dictionaries_map(ids, session=session)
    except Exception as exc:
        logger.warning("Failed to batch-fetch data dictionaries: %s", exc)
        return {resource_id: [] for resource_id in ids}

    return {
        resource_id: sanitize_for_json(
            serialize_resource_data_dictionaries(dictionaries_by_id.get(resource_id, []))
        )
        for resource_id in ids
    }


async def _build_batch_context(batch: list[dict[str, Any]]) -> ResourceBatchContext:
    resource_ids = [str(resource.get("id") or "") for resource in batch if resource.get("id")]
    if not resource_ids:
        return ResourceBatchContext({}, {}, {}, {}, {}, {})

    (
        distribution_contexts,
        allmaps_attributes,
        bridge_asset_download_rows,
        relationships,
        thumbnail_asset_urls,
        data_dictionaries,
    ) = await asyncio.gather(
        fetch_distribution_context_map(resource_ids),
        _fetch_allmaps_attributes_map(resource_ids),
        _fetch_bridge_asset_download_rows_map(resource_ids),
        _fetch_relationships_map(resource_ids),
        _fetch_thumbnail_asset_url_map(resource_ids),
        _fetch_data_dictionaries_map(resource_ids),
    )

    distribution_contexts = {
        resource_id: distribution_contexts.get(
            resource_id,
            build_distribution_context(resource_id, []),
        )
        for resource_id in resource_ids
    }

    return ResourceBatchContext(
        distribution_contexts=distribution_contexts,
        allmaps_attributes=allmaps_attributes,
        bridge_asset_download_rows=bridge_asset_download_rows,
        relationships=relationships,
        thumbnail_asset_urls=thumbnail_asset_urls,
        data_dictionaries=data_dictionaries,
    )


async def _prime_resource_representation(
    resource_dict: dict[str, Any],
    *,
    batch_context: ResourceBatchContext | None = None,
    store: bool = True,
) -> tuple[str, str, dict[str, Any] | None]:
    resource_id = str(resource_dict.get("id") or "")
    if not resource_id:
        return ("failed", "missing resource id", None)

    try:
        if batch_context is None:
            async with async_session_factory() as session:
                resource = await process_resource(
                    resource_dict,
                    session,
                    include_similar_items=False,
                )
        else:
            resource = await process_resource(
                resource_dict,
                None,
                include_similar_items=False,
                distribution_context=batch_context.distribution_contexts[resource_id],
                bridge_asset_download_rows=batch_context.bridge_asset_download_rows.get(
                    resource_id,
                    [],
                ),
                ui_relationships=batch_context.relationships.get(resource_id, {}),
                allmaps_attributes=batch_context.allmaps_attributes.get(resource_id, {}),
                data_dictionaries_payload=batch_context.data_dictionaries.get(resource_id, []),
                thumbnail_asset_url=batch_context.thumbnail_asset_urls.get(resource_id),
            )
        if store:
            await store_resource_representation(resource_id, resource)
        return ("primed", resource_id, resource)
    except Exception as exc:
        logger.warning("Failed to prime resource representation %s: %s", resource_id, exc)
        return ("failed", resource_id, None)


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

    batch_context = await _build_batch_context(to_prime)
    semaphore = asyncio.Semaphore(max(1, concurrency))

    async def run_one(resource: dict[str, Any]) -> tuple[str, str, dict[str, Any] | None]:
        async with semaphore:
            return await _prime_resource_representation(
                resource,
                batch_context=batch_context,
                store=False,
            )

    tasks = [asyncio.create_task(run_one(resource)) for resource in to_prime]
    resources_to_store: dict[str, dict[str, Any]] = {}
    for task in asyncio.as_completed(tasks):
        status, resource_id, resource = await task
        counters[status] += 1
        if status == "primed" and resource is not None:
            resources_to_store[resource_id] = resource
        progress.update(1)

    await store_resource_representations(resources_to_store)
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
    parser.add_argument("--batch-size", type=int, default=500, help="Database batch size")
    parser.add_argument("--concurrency", type=int, default=16, help="Concurrent resource builders")
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
