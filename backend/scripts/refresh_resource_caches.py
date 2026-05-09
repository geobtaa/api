#!/usr/bin/env python3
"""
Purge and rehydrate resource caches for a selected resource set.

For each selected resource this script:
- invalidates Redis L1 entries tagged with resource:<id>
- deletes durable endpoint-response L2 rows in generated_api_responses via tags
- deletes durable resource-representation L2 rows in generated_resource_representations
- rebuilds resource representations with the existing primer, which writes durable
  rows before Redis hot entries
- optionally warms resource detail endpoint responses

Selectors are intentionally resource-based, not field-specific:
  python scripts/refresh_resource_caches.py stanford-fd113yz1610 --apply
  python scripts/refresh_resource_caches.py --ids-file tmp/ids.txt --apply
  python scripts/refresh_resource_caches.py --where-file tmp/resource_where.sql --apply
  python scripts/refresh_resource_caches.py --query-file tmp/resource_ids.sql --apply
  python scripts/refresh_resource_caches.py --all --limit 100 --apply
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import text

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)

DEFAULT_RESOURCE_WARM_PATHS = (
    "/api/v1/resources/{id}",
    "/api/v1/resources/{id}?format=json",
)


def _dedupe_preserve_order(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = str(value or "").strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned)
    return result


def _read_lines(path: str | None) -> list[str]:
    if not path:
        return []
    return [
        line.strip()
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def _read_where(path: str | None, inline_where: str | None) -> str | None:
    if path:
        where = Path(path).read_text(encoding="utf-8").strip()
        return where or None
    if inline_where:
        where = inline_where.strip()
        return where or None
    return None


def _read_query(path: str | None, inline_query: str | None) -> str | None:
    if path:
        query = Path(path).read_text(encoding="utf-8").strip().rstrip(";")
        return query or None
    if inline_query:
        query = inline_query.strip().rstrip(";")
        return query or None
    return None


def configure_logging(*, verbose: bool = False) -> None:
    """Keep bulk refresh output readable unless verbose diagnostics are requested."""
    level = logging.INFO if verbose else logging.WARNING
    logging.basicConfig(level=level, format="%(levelname)s: %(message)s", force=True)
    for handler in logging.getLogger().handlers:
        handler.setLevel(level)


async def _query_resource_ids(
    *,
    all_resources: bool,
    where: str | None,
    query: str | None,
    limit: int | None,
) -> list[str]:
    if not all_resources and not where and not query:
        return []

    if query:
        sql = f"SELECT id FROM ({query}) selected_resource_ids"
    else:
        sql = "SELECT id FROM resources"
        if where:
            sql = f"{sql} WHERE {where}"
        sql = f"{sql} ORDER BY id"
    if limit is not None:
        sql = f"{sql} LIMIT :limit"

    values = {"limit": max(0, int(limit))} if limit is not None else {}
    from app.services.distribution_repository import async_session_factory

    async with async_session_factory() as session:
        result = await session.execute(text(sql), values)
        return [str(row[0]) for row in result.fetchall()]


async def select_resource_ids(
    *,
    positional_ids: Iterable[str],
    ids_file: str | None,
    all_resources: bool,
    where: str | None,
    query: str | None,
    limit: int | None,
) -> list[str]:
    explicit_ids = _dedupe_preserve_order([*positional_ids, *_read_lines(ids_file)])
    queried_ids = await _query_resource_ids(
        all_resources=all_resources,
        where=where,
        query=query,
        limit=limit,
    )
    ids = _dedupe_preserve_order([*explicit_ids, *queried_ids])
    if limit is not None and explicit_ids and not queried_ids:
        return ids[: max(0, int(limit))]
    return ids


def _resource_tags(resource_ids: Iterable[str]) -> list[str]:
    return [f"resource:{resource_id}" for resource_id in resource_ids]


def _warm_path_from_record(record: dict[str, Any]) -> str | None:
    warm = record.get("warm")
    if not isinstance(warm, dict):
        return None
    if str(warm.get("method") or "GET").upper() != "GET":
        return None
    path = str(warm.get("path") or "").strip()
    if not path.startswith("/"):
        return None
    query = str(warm.get("query") or "").strip()
    return f"{path}?{query}" if query else path


def _default_warm_paths(resource_ids: Iterable[str]) -> list[str]:
    return [
        template.format(id=resource_id)
        for resource_id in resource_ids
        for template in DEFAULT_RESOURCE_WARM_PATHS
    ]


async def purge_resource_caches(
    resource_ids: list[str],
    *,
    collect_tagged_paths: bool,
) -> dict[str, Any]:
    from app.services.cache_service import CacheService
    from app.services.resource_representation_cache import (
        delete_resource_representations,
    )

    cache = CacheService()
    tags = _resource_tags(resource_ids)
    tagged_records = await cache.cached_records_for_tags(tags) if collect_tagged_paths else []
    tagged_paths = [
        path for path in (_warm_path_from_record(record) for record in tagged_records) if path
    ]

    representation_delete_stats = await delete_resource_representations(
        resource_ids,
        cache_service=cache,
    )
    tagged_cache_entries_deleted = await cache.invalidate_tags(tags)

    return {
        "tagged_records": len(tagged_records),
        "tagged_paths": tagged_paths,
        "resource_representations_cleared": representation_delete_stats,
        "tagged_cache_entries_deleted": tagged_cache_entries_deleted,
    }


async def rehydrate_resource_representations(
    resource_ids: list[str],
    *,
    batch_size: int,
    concurrency: int,
) -> Counter:
    from scripts.prime_resource_representation_cache import prime_resource_representation_cache

    return await prime_resource_representation_cache(
        resource_ids=resource_ids,
        limit=None,
        batch_size=max(1, batch_size),
        concurrency=max(1, concurrency),
        force=True,
    )


async def warm_endpoint_caches(
    resource_ids: list[str],
    *,
    tagged_paths: Iterable[str],
    include_tagged_paths: bool,
    max_paths: int,
    concurrency: int,
    timeout_seconds: float,
) -> dict[str, int]:
    paths = _default_warm_paths(resource_ids)
    if include_tagged_paths:
        paths.extend(tagged_paths)
    paths = _dedupe_preserve_order(paths)[: max(0, max_paths)]
    if not paths:
        return {"attempted": 0, "warmed": 0, "errors": 0}

    from app.main import app

    counters: Counter[str] = Counter()
    semaphore = asyncio.Semaphore(max(1, concurrency))
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://resource-cache-refresh.local",
        timeout=timeout_seconds,
    ) as client:

        async def warm_one(path: str) -> None:
            async with semaphore:
                try:
                    response = await client.get(path, headers={"Accept": "application/json"})
                    if 200 <= response.status_code < 300:
                        counters["warmed"] += 1
                    else:
                        counters["errors"] += 1
                        logger.warning(
                            "Endpoint cache warm returned status=%s path=%s",
                            response.status_code,
                            path,
                        )
                except Exception as exc:
                    counters["errors"] += 1
                    logger.warning("Endpoint cache warm failed path=%s err=%s", path, exc)

        await asyncio.gather(*(warm_one(path) for path in paths))

    return {
        "attempted": len(paths),
        "warmed": counters["warmed"],
        "errors": counters["errors"],
    }


async def refresh_resource_caches(
    resource_ids: list[str],
    *,
    apply: bool,
    batch_size: int,
    concurrency: int,
    skip_rehydrate: bool,
    skip_endpoint_warm: bool,
    warm_tagged_paths: bool,
    max_warm_paths: int,
    warm_timeout_seconds: float,
) -> dict[str, Any]:
    stats: dict[str, Any] = {
        "apply": apply,
        "resource_ids": len(resource_ids),
    }
    if not resource_ids:
        return stats
    if not apply:
        stats["sample_resource_ids"] = resource_ids[:20]
        stats["message"] = "Dry run only; pass --apply to purge and rehydrate caches."
        return stats

    purge_stats = await purge_resource_caches(
        resource_ids,
        collect_tagged_paths=warm_tagged_paths,
    )
    tagged_paths = purge_stats.pop("tagged_paths", [])
    stats.update(purge_stats)

    if not skip_rehydrate:
        counters = await rehydrate_resource_representations(
            resource_ids,
            batch_size=batch_size,
            concurrency=concurrency,
        )
        stats["resource_representations"] = dict(counters)

    if not skip_endpoint_warm:
        stats["endpoint_warm"] = await warm_endpoint_caches(
            resource_ids,
            tagged_paths=tagged_paths,
            include_tagged_paths=warm_tagged_paths,
            max_paths=max_warm_paths,
            concurrency=concurrency,
            timeout_seconds=warm_timeout_seconds,
        )

    return stats


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Purge and rehydrate caches for selected resources."
    )
    parser.add_argument("resource_ids", nargs="*", help="Explicit resource IDs to refresh")
    parser.add_argument("--ids-file", help="File with one resource ID per line")
    parser.add_argument("--all", action="store_true", help="Select all resources")
    parser.add_argument(
        "--where",
        help="Trusted SQL WHERE clause against resources for selecting IDs",
    )
    parser.add_argument(
        "--where-file",
        help="File containing a trusted SQL WHERE clause against resources",
    )
    parser.add_argument(
        "--query",
        help="Trusted SQL SELECT id query for selecting resource IDs",
    )
    parser.add_argument(
        "--query-file",
        help="File containing a trusted SQL SELECT id query for selecting resource IDs",
    )
    parser.add_argument("--limit", type=int, help="Limit selected resources")
    parser.add_argument("--apply", action="store_true", help="Actually purge and rehydrate")
    parser.add_argument("--batch-size", type=int, default=500, help="Primer batch size")
    parser.add_argument("--concurrency", type=int, default=16, help="Concurrent builders/warmers")
    parser.add_argument(
        "--skip-rehydrate",
        action="store_true",
        help="Only purge caches; do not rebuild resource representation caches",
    )
    parser.add_argument(
        "--skip-endpoint-warm",
        action="store_true",
        help="Do not warm /api/v1/resources/{id} endpoint response caches",
    )
    parser.add_argument(
        "--warm-tagged-paths",
        action="store_true",
        help="Also rewarm previously cached GET paths tagged by the selected resources",
    )
    parser.add_argument(
        "--max-warm-paths",
        type=int,
        default=5000,
        help="Maximum endpoint paths to warm",
    )
    parser.add_argument(
        "--warm-timeout-seconds",
        type=float,
        default=20.0,
        help="Timeout for in-process endpoint warming requests",
    )
    parser.add_argument("--verbose", action="store_true", help="Show INFO logs")
    return parser.parse_args()


async def _main_async() -> int:
    args = _parse_args()
    configure_logging(verbose=args.verbose)

    where = _read_where(args.where_file, args.where)
    query = _read_query(args.query_file, args.query)
    try:
        resource_ids = await select_resource_ids(
            positional_ids=args.resource_ids,
            ids_file=args.ids_file,
            all_resources=bool(args.all),
            where=where,
            query=query,
            limit=args.limit,
        )
    except Exception as exc:
        print(f"Failed to select resources: {exc}")
        return 1
    if not resource_ids:
        print(
            "No resources selected. Provide resource IDs, --ids-file, --where/--where-file, "
            "--query/--query-file, or --all."
        )
        return 2

    stats = await refresh_resource_caches(
        resource_ids,
        apply=bool(args.apply),
        batch_size=max(1, args.batch_size),
        concurrency=max(1, args.concurrency),
        skip_rehydrate=bool(args.skip_rehydrate),
        skip_endpoint_warm=bool(args.skip_endpoint_warm),
        warm_tagged_paths=bool(args.warm_tagged_paths),
        max_warm_paths=max(0, args.max_warm_paths),
        warm_timeout_seconds=max(0.1, args.warm_timeout_seconds),
    )
    for key, value in stats.items():
        print(f"{key}: {value}")

    representation_stats = stats.get("resource_representations")
    endpoint_stats = stats.get("endpoint_warm")
    if isinstance(representation_stats, dict) and representation_stats.get("failed"):
        return 1
    if isinstance(endpoint_stats, dict) and endpoint_stats.get("errors"):
        return 1
    return 0


def main() -> int:
    return asyncio.run(_main_async())


if __name__ == "__main__":
    raise SystemExit(main())
