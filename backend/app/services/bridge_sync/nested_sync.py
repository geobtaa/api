from __future__ import annotations

from typing import Any, Dict, List, Tuple

from sqlalchemy import delete, insert

from db.database import database
from db.models import (
    resource_assets,
    resource_downloads,
    resource_licensed_accesses,
)


def _group_by_resource(
    batch: List[Dict[str, Any]],
) -> Tuple[
    Dict[str, List[Dict[str, Any]]],
    Dict[str, List[Dict[str, Any]]],
    Dict[str, List[Dict[str, Any]]],
]:
    by_downloads: Dict[str, List[Dict[str, Any]]] = {}
    by_licensed: Dict[str, List[Dict[str, Any]]] = {}
    by_assets: Dict[str, List[Dict[str, Any]]] = {}

    for item in batch:
        rid = str(item.get("resource_id") or "").strip()
        if not rid:
            continue

        for d in item.get("document_downloads") or []:
            by_downloads.setdefault(rid, []).append(d or {})

        for a in item.get("document_licensed_accesses") or []:
            by_licensed.setdefault(rid, []).append(a or {})

        for asset in item.get("assets") or []:
            by_assets.setdefault(rid, []).append(asset or {})

    return by_downloads, by_licensed, by_assets


async def _sync_downloads(grouped: Dict[str, List[Dict[str, Any]]]) -> None:
    for rid, downloads in grouped.items():
        await database.execute(
            delete(resource_downloads).where(resource_downloads.c.resource_id == rid)
        )
        if not downloads:
            continue

        rows = []
        for d in downloads:
            rows.append(
                {
                    "resource_id": rid,
                    "label": d.get("label"),
                    "value": d.get("value"),
                    "position": d.get("position") or 0,
                }
            )
        if rows:
            query = insert(resource_downloads)
            await database.execute_many(query, rows)


async def _sync_licensed_accesses(grouped: Dict[str, List[Dict[str, Any]]]) -> None:
    for rid, accesses in grouped.items():
        await database.execute(
            delete(resource_licensed_accesses).where(
                resource_licensed_accesses.c.resource_id == rid
            )
        )
        if not accesses:
            continue

        rows = []
        for a in accesses:
            rows.append(
                {
                    "resource_id": rid,
                    "institution_code": a.get("institution_code"),
                    "access_url": a.get("access_url") or a.get("url"),
                    "legacy_friendlier_id": a.get("friendlier_id"),
                }
            )
        if rows:
            query = insert(resource_licensed_accesses)
            await database.execute_many(query, rows)


async def _sync_assets(grouped: Dict[str, List[Dict[str, Any]]]) -> None:
    for rid, assets in grouped.items():
        await database.execute(delete(resource_assets).where(resource_assets.c.resource_id == rid))
        if not assets:
            continue

        rows = []
        for asset in assets:
            file = asset.get("file") or {}
            meta = file.get("metadata") or {}
            rows.append(
                {
                    "resource_id": rid,
                    "bridge_asset_id": asset.get("id"),
                    "bridge_parent_id": asset.get("parent_id"),
                    "friendlier_id": asset.get("friendlier_id"),
                    "title": asset.get("title"),
                    "label": asset.get("label"),
                    "thumbnail": bool(asset.get("thumbnail")),
                    "dct_references_uri_key": asset.get("dct_references_uri_key"),
                    "position": asset.get("position") or 0,
                    "file_url": (file.get("url") or "") or None,
                    "file_mime_type": meta.get("mime_type"),
                    "file_size": meta.get("size"),
                    "file_width": meta.get("width"),
                    "file_height": meta.get("height"),
                    "file_md5": meta.get("md5"),
                    "file_sha1": meta.get("sha1"),
                    "file_sha512": meta.get("sha512"),
                }
            )
        if rows:
            query = insert(resource_assets)
            await database.execute_many(query, rows)


async def sync_nested_for_batch(batch: List[Dict[str, Any]]) -> None:
    """
    Sync bridge-provided nested collections for a batch of resources.

    Expected batch item shape:
    {
      "resource_id": "...",
      "document_downloads": [...],
      "document_licensed_accesses": [...],
      "assets": [...]
    }
    """
    if not batch:
        return

    by_downloads, by_licensed, by_assets = _group_by_resource(batch)

    if by_downloads:
        await _sync_downloads(by_downloads)
    if by_licensed:
        await _sync_licensed_accesses(by_licensed)
    if by_assets:
        await _sync_assets(by_assets)
