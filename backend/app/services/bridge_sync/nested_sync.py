from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from sqlalchemy import delete, insert, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from db.database import database
from db.models import (
    resource_assets,
    resource_data_dictionaries,
    resource_data_dictionary_entries,
    resource_downloads,
    resource_licensed_accesses,
)


def _nested_dict_rows(value: Any, *, field: str, resource_id: str) -> List[Dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ValueError(f"{field} must be an array of objects for resource {resource_id}")
    return value


def _group_by_resource(
    batch: List[Dict[str, Any]],
) -> Tuple[
    Dict[str, Dict[str, Any]],
    Dict[str, List[Dict[str, Any]]],
    Dict[str, List[Dict[str, Any]]],
    Dict[str, List[Dict[str, Any]]],
]:
    by_data_dictionaries: Dict[str, Dict[str, Any]] = {}
    by_downloads: Dict[str, List[Dict[str, Any]]] = {}
    by_licensed: Dict[str, List[Dict[str, Any]]] = {}
    by_assets: Dict[str, List[Dict[str, Any]]] = {}

    for item in batch:
        rid = str(item.get("resource_id") or "").strip()
        if not rid:
            continue

        if "document_data_dictionaries" in item:
            payload = by_data_dictionaries.setdefault(rid, {})
            payload.setdefault("dictionaries", []).extend(
                _nested_dict_rows(
                    item.get("document_data_dictionaries"),
                    field="document_data_dictionaries",
                    resource_id=rid,
                )
            )
        if "document_data_dictionary_entries" in item:
            payload = by_data_dictionaries.setdefault(rid, {})
            payload.setdefault("entries", []).extend(
                _nested_dict_rows(
                    item.get("document_data_dictionary_entries"),
                    field="document_data_dictionary_entries",
                    resource_id=rid,
                )
            )

        if "document_downloads" in item:
            downloads = by_downloads.setdefault(rid, [])
            for d in item.get("document_downloads") or []:
                downloads.append(d or {})

        if "document_licensed_accesses" in item:
            licensed = by_licensed.setdefault(rid, [])
            for a in item.get("document_licensed_accesses") or []:
                licensed.append(a or {})

        if "assets" in item:
            assets = by_assets.setdefault(rid, [])
            for asset in item.get("assets") or []:
                assets.append(asset or {})

    return by_data_dictionaries, by_downloads, by_licensed, by_assets


def _optional_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _timestamp(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None

    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _text_value(value: Any) -> str | None:
    if value is None or isinstance(value, str):
        return value
    return json.dumps(value, sort_keys=True)


async def _sync_data_dictionaries(
    grouped: Dict[str, Dict[str, Any]],
) -> None:
    for rid, payload in grouped.items():
        dictionaries_present = "dictionaries" in payload
        entries_present = "entries" in payload
        source_dictionaries = payload.get("dictionaries") or []
        source_entries = payload.get("entries") or []
        source_to_local_dictionary_id: Dict[int, int] = {}

        if dictionaries_present:
            for dictionary in source_dictionaries:
                source_dictionary_id = _optional_int(dictionary.get("id"))
                if source_dictionary_id is None:
                    raise ValueError(f"data dictionary is missing an id for resource {rid}")

                values: Dict[str, Any] = {
                    "resource_id": rid,
                    "legacy_document_data_dictionary_id": source_dictionary_id,
                }
                for field in ("name", "description", "staff_notes"):
                    if field in dictionary:
                        values[field] = dictionary.get(field)
                if "tags" in dictionary:
                    values["tags"] = _text_value(dictionary.get("tags")) or ""
                position = _optional_int(dictionary.get("position"))
                if position is not None:
                    values["position"] = position
                for field in ("created_at", "updated_at"):
                    timestamp = _timestamp(dictionary.get(field))
                    if timestamp is not None:
                        values[field] = timestamp

                stmt = pg_insert(resource_data_dictionaries).values(values)
                update_values = {
                    "resource_id": stmt.excluded.resource_id,
                    **{
                        field: stmt.excluded[field]
                        for field in (
                            "name",
                            "description",
                            "staff_notes",
                            "tags",
                            "position",
                            "updated_at",
                        )
                        if field in values
                    },
                }
                stmt = stmt.on_conflict_do_update(
                    index_elements=[
                        resource_data_dictionaries.c.legacy_document_data_dictionary_id
                    ],
                    set_=update_values,
                ).returning(resource_data_dictionaries.c.id)
                local_dictionary_id = await database.fetch_val(stmt)
                if local_dictionary_id is not None:
                    source_to_local_dictionary_id[source_dictionary_id] = int(local_dictionary_id)

            source_dictionary_ids = list(source_to_local_dictionary_id)
            delete_stale_dictionaries = delete(resource_data_dictionaries).where(
                resource_data_dictionaries.c.resource_id == rid
            )
            if source_dictionary_ids:
                delete_stale_dictionaries = delete_stale_dictionaries.where(
                    or_(
                        resource_data_dictionaries.c.legacy_document_data_dictionary_id.is_(None),
                        resource_data_dictionaries.c.legacy_document_data_dictionary_id.not_in(
                            source_dictionary_ids
                        ),
                    )
                )
            await database.execute(delete_stale_dictionaries)

        if not entries_present:
            continue

        if not dictionaries_present:
            existing_dictionaries = await database.fetch_all(
                select(
                    resource_data_dictionaries.c.id,
                    resource_data_dictionaries.c.legacy_document_data_dictionary_id,
                ).where(resource_data_dictionaries.c.resource_id == rid)
            )
            source_to_local_dictionary_id = {
                int(row["legacy_document_data_dictionary_id"]): int(row["id"])
                for row in existing_dictionaries
                if row["legacy_document_data_dictionary_id"] is not None
            }

        if not source_to_local_dictionary_id:
            continue

        source_entry_ids: List[int] = []
        for entry in source_entries:
            source_entry_id = _optional_int(entry.get("id"))
            source_dictionary_id = _optional_int(entry.get("document_data_dictionary_id"))
            local_dictionary_id = source_to_local_dictionary_id.get(
                source_dictionary_id if source_dictionary_id is not None else -1
            )
            field_name = str(entry.get("field_name") or "").strip()
            if source_entry_id is None:
                raise ValueError(f"data dictionary entry is missing an id for resource {rid}")
            if local_dictionary_id is None:
                raise ValueError(
                    f"data dictionary entry references an unknown dictionary for resource {rid}"
                )
            if not field_name:
                raise ValueError(f"data dictionary entry {source_entry_id} is missing a field name")

            values = {
                "resource_data_dictionary_id": local_dictionary_id,
                "legacy_document_data_dictionary_entry_id": source_entry_id,
                "field_name": field_name,
                "field_type": _text_value(entry.get("field_type")),
                "values": _text_value(entry.get("values")),
                "definition": _text_value(entry.get("definition")),
                "definition_source": _text_value(entry.get("definition_source")),
                "parent_field_name": _text_value(entry.get("parent_field_name")),
                "position": _optional_int(entry.get("position")) or 0,
            }
            for field in ("created_at", "updated_at"):
                timestamp = _timestamp(entry.get(field))
                if timestamp is not None:
                    values[field] = timestamp

            stmt = pg_insert(resource_data_dictionary_entries).values(values)
            stmt = stmt.on_conflict_do_update(
                index_elements=[
                    resource_data_dictionary_entries.c.legacy_document_data_dictionary_entry_id
                ],
                set_={
                    field: stmt.excluded[field]
                    for field in (
                        "resource_data_dictionary_id",
                        "field_name",
                        "field_type",
                        "values",
                        "definition",
                        "definition_source",
                        "parent_field_name",
                        "position",
                        "updated_at",
                    )
                    if field in values
                },
            )
            await database.execute(stmt)
            source_entry_ids.append(source_entry_id)

        local_dictionary_ids = list(source_to_local_dictionary_id.values())
        delete_stale_entries = delete(resource_data_dictionary_entries).where(
            resource_data_dictionary_entries.c.resource_data_dictionary_id.in_(local_dictionary_ids)
        )
        if source_entry_ids:
            delete_stale_entries = delete_stale_entries.where(
                or_(
                    resource_data_dictionary_entries.c.legacy_document_data_dictionary_entry_id.is_(
                        None
                    ),
                    resource_data_dictionary_entries.c.legacy_document_data_dictionary_entry_id.not_in(
                        source_entry_ids
                    ),
                )
            )
        await database.execute(delete_stale_entries)


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
      "document_data_dictionaries": [...],
      "document_data_dictionary_entries": [...],
      "document_downloads": [...],
      "document_licensed_accesses": [...],
      "assets": [...]
    }
    """
    if not batch:
        return

    by_data_dictionaries, by_downloads, by_licensed, by_assets = _group_by_resource(batch)

    if by_data_dictionaries:
        await _sync_data_dictionaries(by_data_dictionaries)
    if by_downloads:
        await _sync_downloads(by_downloads)
    if by_licensed:
        await _sync_licensed_accesses(by_licensed)
    if by_assets:
        await _sync_assets(by_assets)
