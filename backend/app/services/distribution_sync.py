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

from db.database import database
from db.models import distribution_types, resource_distributions

logger = logging.getLogger(__name__)

# Cache of distribution_uri -> type_id (rarely changes)
_uri_to_type_id: Optional[Dict[str, int]] = None


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


def clear_uri_cache() -> None:
    """Clear the cached uri->type_id mapping (e.g. after distribution_types changes)."""
    global _uri_to_type_id
    _uri_to_type_id = None
