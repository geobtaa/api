from __future__ import annotations

import logging
import os
from typing import Any, Iterable

from sqlalchemy import select

from app.elasticsearch.client import es
from app.elasticsearch.index import process_resource
from db.database import database
from db.models import resources

logger = logging.getLogger(__name__)
DEFAULT_REFRESH_BATCH_SIZE = 5000


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "t", "yes", "y"}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError:
        logger.warning("Invalid integer for %s=%r; using default=%s", name, value, default)
        return default
    if parsed < 1:
        logger.warning(
            "Invalid non-positive integer for %s=%r; using default=%s", name, value, default
        )
        return default
    return parsed


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


def _refresh_batch_size() -> int:
    # BRIDGE_SEARCH_INDEX_MAX_RESOURCE_IDS used to be a total cap. Keep it as
    # a compatibility alias, but interpret it as batch size so no IDs are lost.
    legacy_batch_size = _env_int("BRIDGE_SEARCH_INDEX_MAX_RESOURCE_IDS", DEFAULT_REFRESH_BATCH_SIZE)
    return _env_int("BRIDGE_SEARCH_INDEX_BATCH_SIZE", legacy_batch_size)


def _chunk_list(values: list[str], size: int) -> Iterable[list[str]]:
    for start in range(0, len(values), size):
        yield values[start : start + size]


async def _index_changed_resource_batch(
    batch_ids: list[str],
    *,
    index_name: str,
) -> dict[str, int]:
    rows = await database.fetch_all(select(resources).where(resources.c.id.in_(batch_ids)))
    rows_by_id = {str(row["id"]): dict(row) for row in rows}

    indexed = 0
    errors = 0
    missing = 0

    for resource_id in batch_ids:
        row = rows_by_id.get(resource_id)
        if not row:
            missing += 1
            try:
                await es.delete(index=index_name, id=resource_id, ignore_status=[404])
            except Exception as exc:
                errors += 1
                logger.warning(
                    "Failed deleting missing bridge resource from ES id=%s: %s",
                    resource_id,
                    exc,
                )
            continue

        try:
            document = await process_resource(row)
            if not document:
                errors += 1
                continue
            await es.index(index=index_name, id=resource_id, document=document)
            indexed += 1
        except Exception as exc:
            errors += 1
            logger.warning("Failed indexing bridge resource id=%s: %s", resource_id, exc)

    return {"indexed": indexed, "missing": missing, "errors": errors}


async def index_changed_resources(resource_ids: Iterable[str]) -> dict[str, Any]:
    """Targeted Elasticsearch refresh for resources imported by bridge delta sync."""

    if not _env_bool("BRIDGE_SEARCH_INDEX_REFRESH_ENABLED", True):
        return {"enabled": False, "resource_ids": 0, "indexed": 0, "errors": 0}

    changed_ids = _dedupe_preserve_order(resource_ids)
    if not changed_ids:
        return {"enabled": True, "resource_ids": 0, "indexed": 0, "errors": 0}

    if not database.is_connected:
        await database.connect()

    index_name = os.getenv("ELASTICSEARCH_INDEX", "btaa_geospatial_api")
    batch_size = _refresh_batch_size()
    batches = 0
    indexed = 0
    errors = 0
    missing = 0

    for batch_ids in _chunk_list(changed_ids, batch_size):
        batches += 1
        batch_stats = await _index_changed_resource_batch(batch_ids, index_name=index_name)
        indexed += batch_stats["indexed"]
        missing += batch_stats["missing"]
        errors += batch_stats["errors"]

    try:
        await es.indices.refresh(index=index_name)
    except Exception as exc:
        logger.warning("Failed refreshing Elasticsearch index after bridge delta: %s", exc)

    stats = {
        "enabled": True,
        "resource_ids": len(changed_ids),
        "batch_size": batch_size,
        "batches": batches,
        "indexed": indexed,
        "missing": missing,
        "errors": errors,
    }
    logger.info("Bridge search index refresh complete: %s", stats)
    return stats
