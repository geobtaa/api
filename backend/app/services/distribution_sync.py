"""
Sync resource distributions from dct_references_s.

Used by OGM harvest to populate resource_distributions when importing/updating
resources, and by the backfill script for existing resources.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import delete, insert, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from db.database import database
from db.models import distribution_types, resource_distributions

logger = logging.getLogger(__name__)

# Cache of distribution_uri -> type_id (rarely changes)
_uri_to_type_id: Optional[Dict[str, int]] = None
# Cache of valid distribution_type ids (for bridge document_distributions mapping)
_valid_type_ids: Optional[set[int]] = None
# Cache of distribution_type id -> distribution_uri for legacy bridge mappings
_type_id_to_uri: Optional[Dict[int, str]] = None


async def _get_uri_to_type_id() -> Dict[str, int]:
    """Load distribution_uri -> type_id mapping from distribution_types."""
    global _uri_to_type_id
    if _uri_to_type_id is not None:
        return _uri_to_type_id
    rows = await database.fetch_all(
        select(distribution_types.c.id, distribution_types.c.distribution_uri)
    )
    _uri_to_type_id = {str(r["distribution_uri"]): int(r["id"]) for r in rows}
    return _uri_to_type_id


async def _get_valid_type_ids() -> set[int]:
    """Load the set of valid distribution_type primary keys."""
    global _valid_type_ids
    if _valid_type_ids is not None:
        return _valid_type_ids
    rows = await database.fetch_all(select(distribution_types.c.id))
    _valid_type_ids = {int(r["id"]) for r in rows}
    return _valid_type_ids


async def get_distribution_type_id_to_uri() -> Dict[int, str]:
    """Load distribution_type primary key -> distribution URI mapping."""
    global _type_id_to_uri
    if _type_id_to_uri is not None:
        return _type_id_to_uri
    rows = await database.fetch_all(
        select(distribution_types.c.id, distribution_types.c.distribution_uri)
    )
    _type_id_to_uri = {int(r["id"]): str(r["distribution_uri"]) for r in rows}
    return _type_id_to_uri


def _parse_references(dct_references_s: Any) -> Optional[Dict[str, Any]]:
    """Parse dct_references_s into a dict of uri -> url or url list."""
    if dct_references_s is None:
        return None
    if isinstance(dct_references_s, dict):
        return dct_references_s
    if isinstance(dct_references_s, str):
        try:
            parsed = json.loads(dct_references_s)
            return parsed if isinstance(parsed, dict) else None
        except (json.JSONDecodeError, TypeError):
            return None
    return None


def _extract_distribution_rows(
    resource_id: str, references: Dict[str, Any], uri_to_type_id: Dict[str, int]
) -> List[Dict[str, Any]]:
    """
    Extract (resource_id, distribution_type_id, url, label, position) rows
    from references dict. Same logic as populate_resource_distributions.
    """
    rows: List[Dict[str, Any]] = []
    position = 0
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    for uri, url_data in references.items():
        if uri not in uri_to_type_id:
            continue
        type_id = uri_to_type_id[uri]
        if isinstance(url_data, list):
            for item in url_data:
                if isinstance(item, dict):
                    actual_url = item.get("url", "")
                    label = item.get("label", "")
                else:
                    actual_url = str(item)
                    label = ""
                if actual_url:
                    rows.append(
                        {
                            "resource_id": resource_id,
                            "distribution_type_id": type_id,
                            "url": actual_url,
                            "label": label or None,
                            "position": position,
                            "created_at": now,
                            "updated_at": now,
                        }
                    )
                    position += 1
        else:
            url_str = str(url_data)
            if url_str:
                rows.append(
                    {
                        "resource_id": resource_id,
                        "distribution_type_id": type_id,
                        "url": url_str,
                        "label": None,
                        "position": position,
                        "created_at": now,
                        "updated_at": now,
                    }
                )
                position += 1
    return rows


async def sync_distributions_for_resource(resource_id: str, dct_references_s: Any) -> int:
    """
    Sync resource_distributions for a single resource from dct_references_s.
    Deletes existing distributions and inserts new ones.
    Returns the number of distribution rows inserted.
    """
    references = _parse_references(dct_references_s)
    if not references or not isinstance(references, dict):
        await database.execute(
            delete(resource_distributions).where(
                resource_distributions.c.resource_id == resource_id
            )
        )
        return 0

    uri_to_type_id = await _get_uri_to_type_id()
    rows = _extract_distribution_rows(resource_id, references, uri_to_type_id)

    await database.execute(
        delete(resource_distributions).where(resource_distributions.c.resource_id == resource_id)
    )
    for row in rows:
        await database.execute(insert(resource_distributions).values(**row))
    return len(rows)


async def sync_distributions_for_batch(resource_rows: List[Dict[str, Any]]) -> Tuple[int, int]:
    """
    Sync resource_distributions for a batch of resources.
    Each row should have 'id' and 'dct_references_s' keys.
    Returns (synced_count, total_distributions_inserted).
    """
    uri_to_type_id = await _get_uri_to_type_id()
    synced = 0
    total_distributions = 0

    for row in resource_rows:
        resource_id = row.get("id")
        if not resource_id:
            continue
        references = _parse_references(row.get("dct_references_s"))
        if references is None:
            references = {}
        rows_to_insert = _extract_distribution_rows(str(resource_id), references, uri_to_type_id)
        await database.execute(
            delete(resource_distributions).where(
                resource_distributions.c.resource_id == resource_id
            )
        )
        if rows_to_insert:
            for r in rows_to_insert:
                await database.execute(insert(resource_distributions).values(**r))
            synced += 1
            total_distributions += len(rows_to_insert)
    return synced, total_distributions


async def sync_document_distributions_for_batch(
    nested_batch: List[Dict[str, Any]],
) -> Tuple[int, int]:
    """
    Sync resource_distributions from bridge-provided document_distributions.

    Each item in nested_batch should have:
      {
        "resource_id": "...",
        "document_distributions": [
          {
            "reference_type_id": <int>,
            "url": "...",
            "label": "...",
            "position": <int|null>,
            ...
          },
          ...
        ],
        ...
      }

    We map reference_type_id -> distribution_type_id by treating the integer id
    as the primary key in distribution_types when it exists.

    Returns (synced_resources, total_rows_inserted).
    """
    if not nested_batch:
        return 0, 0

    valid_type_ids = await _get_valid_type_ids()
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    rows: List[Dict[str, Any]] = []
    synced_resources = set()

    for item in nested_batch:
        rid = str(item.get("resource_id") or "").strip()
        if not rid:
            continue
        doc_dists = item.get("document_distributions") or []
        if not isinstance(doc_dists, list):
            continue

        for dist in doc_dists:
            if not isinstance(dist, dict):
                continue
            ref_type_id = dist.get("reference_type_id")
            url = (dist.get("url") or "").strip()
            if not url:
                continue
            if not isinstance(ref_type_id, int) or ref_type_id not in valid_type_ids:
                continue

            label = dist.get("label")
            if isinstance(label, str):
                label = label.strip() or None
            else:
                label = None
            position = dist.get("position") or 0

            rows.append(
                {
                    "resource_id": rid,
                    "distribution_type_id": ref_type_id,
                    "url": url,
                    "label": label,
                    "position": position,
                    "created_at": now,
                    "updated_at": now,
                }
            )
            synced_resources.add(rid)

    if not rows:
        return 0, 0

    # Use UPSERT semantics to respect the unique index on
    # (resource_id, distribution_type_id, url) and avoid duplicate-key errors.
    query = pg_insert(resource_distributions)
    upsert_query = query.on_conflict_do_update(
        index_elements=[
            resource_distributions.c.resource_id,
            resource_distributions.c.distribution_type_id,
            resource_distributions.c.url,
        ],
        set_={
            "label": query.excluded.label,
            "position": query.excluded.position,
            "updated_at": query.excluded.updated_at,
        },
    )
    await database.execute_many(upsert_query, rows)
    return len(synced_resources), len(rows)


def clear_uri_cache() -> None:
    """Clear cached mappings (e.g. after distribution_types changes)."""
    global _uri_to_type_id, _valid_type_ids, _type_id_to_uri
    _uri_to_type_id = None
    _valid_type_ids = None
    _type_id_to_uri = None
