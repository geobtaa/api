#!/usr/bin/env python3
"""
Zero-downtime, alias-based reindex for local Docker and Kamal.

Flow:
1) Build a new versioned index: <ELASTICSEARCH_INDEX>_YYYYmmddHHMMSS
2) Index all DB resources into the new index
3) Verify expected counts before cutover
4) Atomically swap alias ELASTICSEARCH_INDEX -> new versioned index
5) Keep one previous versioned index (configurable) and prune older ones

Performance:
- Bulk indexing via Elasticsearch `_bulk`
- Chunk-level prefetch of summaries/spatial facets to avoid N+1 DB queries
- Optional temporary fast index settings during ingest
"""

import asyncio
import json
import logging
import os
import sys
from datetime import UTC, datetime
from time import perf_counter
from typing import Any, TypeVar

from dotenv import load_dotenv

# Add backend/ to import path (scripts/ is under backend/scripts/)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import app.elasticsearch.index as index_module  # noqa: E402
from app.elasticsearch.client import es  # noqa: E402
from app.elasticsearch.index import process_resource  # noqa: E402
from app.elasticsearch.mappings import INDEX_MAPPING  # noqa: E402
from db.database import database  # noqa: E402

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

RETRIABLE_BULK_STATUS = {429, 500, 502, 503, 504}


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "t", "yes", "y"}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        logger.warning("Invalid integer for %s=%r; using default=%s", name, value, default)
        return default


def _build_versioned_index_name(base_alias: str) -> str:
    timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    return f"{base_alias}_{timestamp}"


T = TypeVar("T")


def _chunked(values: list[T], size: int) -> list[list[T]]:
    return [values[i : i + size] for i in range(0, len(values), size)]


async def _create_versioned_index(index_name: str) -> None:
    logger.info("Creating new versioned index: %s", index_name)
    await es.indices.create(
        index=index_name,
        mappings=INDEX_MAPPING["mappings"],
        settings=INDEX_MAPPING["settings"],
    )


async def _db_id_batch(last_id: str | None, chunk_size: int) -> list[str]:
    if last_id is None:
        rows = await database.fetch_all(
            "SELECT id FROM resources ORDER BY id LIMIT :limit", {"limit": chunk_size}
        )
    else:
        rows = await database.fetch_all(
            "SELECT id FROM resources WHERE id > :last_id ORDER BY id LIMIT :limit",
            {"last_id": last_id, "limit": chunk_size},
        )
    return [str(row["id"]) for row in rows]


async def _db_rows_for_ids(ids: list[str]) -> dict[str, dict[str, Any]]:
    if not ids:
        return {}
    placeholders = ", ".join([f":id{i}" for i, _ in enumerate(ids)])
    params = {f"id{i}": rid for i, rid in enumerate(ids)}
    sql = f"SELECT * FROM resources WHERE id IN ({placeholders})"
    rows = await database.fetch_all(sql, params)
    return {str(row["id"]): dict(row) for row in rows}


def _format_spatial_facets_row(row: dict[str, Any]) -> dict[str, Any]:
    spatial_facets: dict[str, Any] = {
        "geo_global": row.get("geo_global"),
        "geo_country": row.get("geo_country"),
        "geo_region": row.get("geo_region"),
        "geo_county": row.get("geo_county"),
    }

    if spatial_facets.get("geo_country"):
        try:
            country_data = json.loads(spatial_facets["geo_country"])
            if (
                isinstance(country_data, dict)
                and "wok_id" in country_data
                and "parent_id" in country_data
                and "name" in country_data
            ):
                spatial_facets["geo_country"] = (
                    f"{country_data['wok_id']}|{country_data['parent_id']}|{country_data['name']}"
                )
            else:
                spatial_facets["geo_country"] = None
        except (json.JSONDecodeError, TypeError):
            spatial_facets["geo_country"] = None

    if spatial_facets.get("geo_region"):
        try:
            region_data = json.loads(spatial_facets["geo_region"])
            if isinstance(region_data, list):
                region_values = []
                for region in region_data:
                    if (
                        isinstance(region, dict)
                        and "wok_id" in region
                        and "parent_id" in region
                        and "name" in region
                    ):
                        region_values.append(
                            f"{region['wok_id']}|{region['parent_id']}|{region['name']}"
                        )
                spatial_facets["geo_region"] = region_values if region_values else None
            else:
                spatial_facets["geo_region"] = None
        except (json.JSONDecodeError, TypeError):
            spatial_facets["geo_region"] = None

    if spatial_facets.get("geo_county"):
        try:
            county_data = json.loads(spatial_facets["geo_county"])
            if isinstance(county_data, list):
                county_values = []
                for county in county_data:
                    if (
                        isinstance(county, dict)
                        and "wok_id" in county
                        and "parent_id" in county
                        and "state_abbrev" in county
                        and "name" in county
                    ):
                        county_values.append(
                            f"{county['wok_id']}|{county['parent_id']}|"
                            f"{county['state_abbrev']}|{county['name']}"
                        )
                spatial_facets["geo_county"] = county_values if county_values else None
            else:
                spatial_facets["geo_county"] = None
        except (json.JSONDecodeError, TypeError):
            spatial_facets["geo_county"] = None

    return spatial_facets


async def _prefetch_summaries_by_id(ids: list[str]) -> dict[str, list[dict[str, Any]]]:
    if not ids:
        return {}

    placeholders = ", ".join([f":id{i}" for i, _ in enumerate(ids)])
    params = {f"id{i}": rid for i, rid in enumerate(ids)}
    sql = f"""
        SELECT resource_id, response, created_at
        FROM resource_ai_enrichments
        WHERE resource_id IN ({placeholders})
        ORDER BY resource_id, created_at DESC
    """
    rows = await database.fetch_all(sql, params)

    summaries_by_id: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        row_dict = dict(row)
        resource_id = str(row_dict["resource_id"])
        if resource_id in summaries_by_id:
            continue  # already kept newest due to ORDER BY ... created_at DESC
        response_data = row_dict.get("response")
        summary_text = ""
        if response_data:
            try:
                if isinstance(response_data, str):
                    parsed = json.loads(response_data)
                else:
                    parsed = response_data
                if isinstance(parsed, dict):
                    summary_text = str(parsed.get("summary", "") or "")
            except (json.JSONDecodeError, TypeError, ValueError):
                summary_text = ""
        summaries_by_id[resource_id] = [{"summary": summary_text}]

    return summaries_by_id


async def _prefetch_spatial_facets_by_id(ids: list[str]) -> dict[str, dict[str, Any]]:
    if not ids:
        return {}

    placeholders = ", ".join([f":id{i}" for i, _ in enumerate(ids)])
    params = {f"id{i}": rid for i, rid in enumerate(ids)}
    sql = f"""
        SELECT resource_id, geo_global, geo_country, geo_region, geo_county
        FROM resource_spatial_facets
        WHERE resource_id IN ({placeholders})
    """
    rows = await database.fetch_all(sql, params)

    return {str(row["resource_id"]): _format_spatial_facets_row(dict(row)) for row in rows}


async def _prepare_documents_for_chunk(ids: list[str]) -> list[tuple[str, dict[str, Any]]]:
    rows_by_id = await _db_rows_for_ids(ids)
    summaries_by_id = await _prefetch_summaries_by_id(ids)
    facets_by_id = await _prefetch_spatial_facets_by_id(ids)

    async def _cached_get_resource_summaries(resource_id: str):
        return summaries_by_id.get(str(resource_id), [])

    async def _cached_get_spatial_facets(resource_id: str):
        return facets_by_id.get(str(resource_id))

    original_get_resource_summaries = index_module.get_resource_summaries
    original_get_spatial_facets = index_module.get_spatial_facets

    index_module.get_resource_summaries = _cached_get_resource_summaries
    index_module.get_spatial_facets = _cached_get_spatial_facets

    documents: list[tuple[str, dict[str, Any]]] = []
    try:
        for resource_id in ids:
            row = rows_by_id.get(resource_id)
            if not row:
                continue
            processed = await process_resource(row)
            if processed:
                documents.append((resource_id, processed))
    finally:
        index_module.get_resource_summaries = original_get_resource_summaries
        index_module.get_spatial_facets = original_get_spatial_facets

    return documents


async def _bulk_index_documents(
    index_name: str,
    documents: list[tuple[str, dict[str, Any]]],
    bulk_size: int,
    max_retries: int,
) -> dict[str, int]:
    created = 0
    updated = 0
    errors = 0

    pending = list(documents)
    attempt = 0

    while pending and attempt <= max_retries:
        if attempt > 0:
            sleep_seconds = min(2**attempt, 8)
            logger.warning(
                "Retrying %s failed docs from previous bulk attempt (attempt %s/%s)",
                len(pending),
                attempt,
                max_retries,
            )
            await asyncio.sleep(sleep_seconds)

        retry_next: list[tuple[str, dict[str, Any]]] = []
        for batch in _chunked(pending, bulk_size):
            operations: list[dict[str, Any]] = []
            for doc_id, doc in batch:
                operations.append({"index": {"_index": index_name, "_id": doc_id}})
                operations.append(doc)

            response = await es.bulk(operations=operations, refresh=False)
            items = response.get("items", [])

            for (doc_id, doc), item in zip(batch, items):
                index_result = item.get("index", {})
                status = int(index_result.get("status", 500))
                result = str(index_result.get("result", ""))

                if 200 <= status < 300:
                    if result == "created":
                        created += 1
                    elif result == "updated":
                        updated += 1
                    else:
                        # Elasticsearch may return "noop" in edge cases.
                        created += 1
                    continue

                if status in RETRIABLE_BULK_STATUS and attempt < max_retries:
                    retry_next.append((doc_id, doc))
                    continue

                errors += 1
                logger.error(
                    "Bulk index failure for id=%s status=%s error=%s",
                    doc_id,
                    status,
                    index_result.get("error"),
                )

        pending = retry_next
        attempt += 1

    if pending:
        # Exceeded retry budget.
        errors += len(pending)
        logger.error("Unresolved bulk indexing failures after retries: %s", len(pending))

    return {
        "total": len(documents),
        "created": created,
        "updated": updated,
        "indexed": created + updated,
        "errors": errors,
    }


async def _apply_fast_index_settings(index_name: str, force_replicas_zero: bool) -> dict[str, str]:
    settings_response = await es.indices.get_settings(index=index_name)
    index_settings = (
        settings_response.get(index_name, {}).get("settings", {}).get("index", {})
    )

    previous = {
        "refresh_interval": str(index_settings.get("refresh_interval", "1s")),
        "number_of_replicas": str(index_settings.get("number_of_replicas", "0")),
    }

    new_settings: dict[str, Any] = {"index": {"refresh_interval": "-1"}}
    if force_replicas_zero:
        new_settings["index"]["number_of_replicas"] = 0

    logger.info("Applying temporary fast index settings to %s: %s", index_name, new_settings)
    await es.indices.put_settings(index=index_name, settings=new_settings)
    return previous


async def _restore_index_settings(index_name: str, previous: dict[str, str]) -> None:
    restore_settings = {
        "index": {
            "refresh_interval": previous["refresh_interval"],
            "number_of_replicas": int(previous["number_of_replicas"]),
        }
    }
    logger.info("Restoring index settings on %s: %s", index_name, restore_settings)
    await es.indices.put_settings(index=index_name, settings=restore_settings)


async def _index_all_resources(
    index_name: str,
    chunk_size: int,
    bulk_size: int,
    bulk_max_retries: int,
    use_fast_settings: bool,
    force_replicas_zero: bool,
    benchmark: bool,
) -> dict[str, int]:
    last_id = None
    attempted = 0
    indexed = 0
    created = 0
    updated = 0
    errors = 0

    db_total = int((await database.fetch_one("SELECT COUNT(*) FROM resources"))[0])
    logger.info("Starting index build for %s resources into %s", db_total, index_name)

    previous_settings: dict[str, str] | None = None
    try:
        if use_fast_settings:
            previous_settings = await _apply_fast_index_settings(index_name, force_replicas_zero)

        while True:
            chunk_start = perf_counter()
            ids = await _db_id_batch(last_id=last_id, chunk_size=chunk_size)
            if not ids:
                break
            last_id = ids[-1]

            prepare_start = perf_counter()
            documents = await _prepare_documents_for_chunk(ids)
            prepare_seconds = perf_counter() - prepare_start
            if documents:
                bulk_start = perf_counter()
                result = await _bulk_index_documents(
                    index_name=index_name,
                    documents=documents,
                    bulk_size=bulk_size,
                    max_retries=bulk_max_retries,
                )
                bulk_seconds = perf_counter() - bulk_start
                attempted += int(result.get("total", len(documents)))
                indexed += int(result.get("indexed", 0))
                created += int(result.get("created", 0))
                updated += int(result.get("updated", 0))
                errors += int(result.get("errors", 0))
            else:
                bulk_seconds = 0.0
            logger.info(
                "Progress: attempted=%s indexed=%s errors=%s (last_id=%s)",
                attempted,
                indexed,
                errors,
                last_id,
            )
            if benchmark:
                logger.info(
                    "Benchmark chunk: ids=%s docs=%s prepare_s=%.3f bulk_s=%.3f total_s=%.3f",
                    len(ids),
                    len(documents),
                    prepare_seconds,
                    bulk_seconds,
                    perf_counter() - chunk_start,
                )
    finally:
        if previous_settings is not None:
            await _restore_index_settings(index_name, previous_settings)

    await es.indices.refresh(index=index_name)
    es_count = int((await es.count(index=index_name)).get("count", 0))

    return {
        "db_total": db_total,
        "attempted": attempted,
        "indexed": indexed,
        "created": created,
        "updated": updated,
        "errors": errors,
        "es_count": es_count,
    }


async def _current_alias_targets(alias_name: str) -> list[str]:
    if not await es.indices.exists_alias(name=alias_name):
        return []
    aliases = await es.indices.get_alias(name=alias_name)
    return sorted(list(aliases.keys()))


async def _all_versioned_indices(base_alias: str) -> list[str]:
    pattern = f"{base_alias}_*"
    try:
        result = await es.indices.get(
            index=pattern,
            allow_no_indices=True,
            ignore_unavailable=True,
            expand_wildcards="open",
        )
    except Exception:
        return []
    return sorted(list(result.keys()), reverse=True)


async def _atomic_alias_swap(
    alias_name: str,
    new_index: str,
    old_alias_targets: list[str],
    legacy_index_exists: bool,
) -> None:
    actions: list[dict[str, Any]] = []

    for old_index in old_alias_targets:
        actions.append({"remove": {"index": old_index, "alias": alias_name}})

    if legacy_index_exists:
        # Bootstrap migration from legacy single physical index -> alias.
        actions.append({"remove_index": {"index": alias_name}})

    actions.append({"add": {"index": new_index, "alias": alias_name}})

    logger.info(
        "Atomically swapping alias '%s' to '%s' (old_targets=%s legacy_index=%s)",
        alias_name,
        new_index,
        old_alias_targets,
        legacy_index_exists,
    )
    await es.indices.update_aliases(actions=actions)


async def _prune_old_versioned_indices(
    base_alias: str,
    new_index: str,
    retain_previous: int,
) -> list[str]:
    versioned = await _all_versioned_indices(base_alias)
    if not versioned:
        return []

    previous = [name for name in versioned if name != new_index]
    keep = {new_index, *previous[: max(retain_previous, 0)]}
    to_delete = [name for name in versioned if name not in keep]

    for index_name in to_delete:
        logger.info("Deleting old versioned index: %s", index_name)
        await es.indices.delete(index=index_name)

    return to_delete


async def main() -> None:
    base_alias = os.getenv("ELASTICSEARCH_INDEX", "btaa_geospatial_api")
    chunk_size = _env_int("REINDEX_ATOMIC_CHUNK_SIZE", 2000)
    bulk_size = _env_int("REINDEX_ATOMIC_BULK_SIZE", 2000)
    bulk_max_retries = _env_int("REINDEX_ATOMIC_BULK_MAX_RETRIES", 2)
    use_fast_settings = _env_bool("REINDEX_ATOMIC_FAST_SETTINGS", True)
    force_replicas_zero = _env_bool("REINDEX_ATOMIC_FORCE_REPLICAS_ZERO", True)
    benchmark = _env_bool("REINDEX_ATOMIC_BENCHMARK", False)
    allow_partial = _env_bool("REINDEX_ATOMIC_ALLOW_PARTIAL", False)
    prune_old = _env_bool("REINDEX_ATOMIC_PRUNE_OLD", True)
    retain_previous = _env_int("REINDEX_ATOMIC_RETAIN_PREVIOUS", 1)
    remove_legacy_index = _env_bool("REINDEX_ATOMIC_REMOVE_LEGACY_INDEX", True)

    if chunk_size <= 0:
        raise ValueError("REINDEX_ATOMIC_CHUNK_SIZE must be > 0")
    if bulk_size <= 0:
        raise ValueError("REINDEX_ATOMIC_BULK_SIZE must be > 0")
    if bulk_max_retries < 0:
        raise ValueError("REINDEX_ATOMIC_BULK_MAX_RETRIES must be >= 0")
    if retain_previous < 0:
        raise ValueError("REINDEX_ATOMIC_RETAIN_PREVIOUS must be >= 0")

    new_index = _build_versioned_index_name(base_alias)

    try:
        overall_start = perf_counter()
        await database.connect()
        create_start = perf_counter()
        await _create_versioned_index(new_index)
        create_seconds = perf_counter() - create_start

        index_start = perf_counter()
        stats = await _index_all_resources(
            index_name=new_index,
            chunk_size=chunk_size,
            bulk_size=bulk_size,
            bulk_max_retries=bulk_max_retries,
            use_fast_settings=use_fast_settings,
            force_replicas_zero=force_replicas_zero,
            benchmark=benchmark,
        )
        index_seconds = perf_counter() - index_start

        if not allow_partial:
            if stats["errors"] > 0:
                raise RuntimeError(
                    f"New index has indexing errors ({stats['errors']}); refusing alias swap"
                )
            if stats["es_count"] != stats["db_total"]:
                raise RuntimeError(
                    "New index count mismatch "
                    f"(db_total={stats['db_total']} es_count={stats['es_count']}); "
                    "refusing alias swap"
                )

        old_alias_targets = await _current_alias_targets(base_alias)
        legacy_index_exists = bool(
            not old_alias_targets and await es.indices.exists(index=base_alias)
        )

        if legacy_index_exists and not remove_legacy_index:
            raise RuntimeError(
                f"Legacy physical index '{base_alias}' exists and blocks alias creation; "
                "set REINDEX_ATOMIC_REMOVE_LEGACY_INDEX=true to migrate."
            )

        alias_start = perf_counter()
        await _atomic_alias_swap(base_alias, new_index, old_alias_targets, legacy_index_exists)
        alias_seconds = perf_counter() - alias_start

        deleted_indices: list[str] = []
        prune_seconds = 0.0
        if prune_old:
            prune_start = perf_counter()
            deleted_indices = await _prune_old_versioned_indices(
                base_alias=base_alias,
                new_index=new_index,
                retain_previous=retain_previous,
            )
            prune_seconds = perf_counter() - prune_start

        logger.info(
            "Atomic reindex complete: alias=%s new_index=%s db_total=%s es_count=%s "
            "indexed=%s errors=%s pruned=%s",
            base_alias,
            new_index,
            stats["db_total"],
            stats["es_count"],
            stats["indexed"],
            stats["errors"],
            len(deleted_indices),
        )
        if benchmark:
            logger.info(
                "Benchmark summary: create_s=%.3f index_s=%.3f alias_swap_s=%.3f "
                "prune_s=%.3f total_s=%.3f",
                create_seconds,
                index_seconds,
                alias_seconds,
                prune_seconds,
                perf_counter() - overall_start,
            )
    finally:
        try:
            await database.disconnect()
        except Exception:
            pass
        try:
            await es.close()
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(main())
