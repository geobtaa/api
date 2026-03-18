from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import (
    resource_data_dictionaries,
    resource_data_dictionary_entries,
)


@dataclass(frozen=True)
class ResourceDataDictionaryEntryRecord:
    id: int
    resource_data_dictionary_id: int
    friendlier_id: str
    field_name: str
    field_type: Optional[str]
    values: Optional[str]
    definition: Optional[str]
    definition_source: Optional[str]
    parent_field_name: Optional[str]
    position: int
    created_at: Optional[datetime]
    updated_at: Optional[datetime]


@dataclass(frozen=True)
class ResourceDataDictionaryRecord:
    id: int
    friendlier_id: str
    name: Optional[str]
    description: Optional[str]
    staff_notes: Optional[str]
    tags: str
    position: int
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    entries: List[ResourceDataDictionaryEntryRecord]


async def fetch_resource_data_dictionaries(
    resource_id: str, *, session: AsyncSession
) -> List[ResourceDataDictionaryRecord]:
    """Fetch dictionaries and entries for a resource, ordered by position."""
    dictionaries_stmt = (
        select(resource_data_dictionaries)
        .where(resource_data_dictionaries.c.resource_id == resource_id)
        .order_by(
            resource_data_dictionaries.c.position,
            resource_data_dictionaries.c.id,
        )
    )
    dictionaries_result = await session.execute(dictionaries_stmt)
    dictionary_rows = dictionaries_result.fetchall()

    if not dictionary_rows:
        return []

    dictionary_ids = [row._mapping["id"] for row in dictionary_rows]

    entries_stmt = (
        select(resource_data_dictionary_entries)
        .where(resource_data_dictionary_entries.c.resource_data_dictionary_id.in_(dictionary_ids))
        .order_by(
            resource_data_dictionary_entries.c.resource_data_dictionary_id,
            resource_data_dictionary_entries.c.position,
            resource_data_dictionary_entries.c.id,
        )
    )
    entries_result = await session.execute(entries_stmt)
    entries_rows = entries_result.fetchall()

    entries_by_dictionary_id: Dict[int, List[ResourceDataDictionaryEntryRecord]] = {}
    for row in entries_rows:
        mapping = row._mapping
        record = ResourceDataDictionaryEntryRecord(
            id=mapping["id"],
            resource_data_dictionary_id=mapping["resource_data_dictionary_id"],
            friendlier_id=resource_id,
            field_name=mapping["field_name"],
            field_type=mapping["field_type"],
            values=mapping["values"],
            definition=mapping["definition"],
            definition_source=mapping["definition_source"],
            parent_field_name=mapping["parent_field_name"],
            position=mapping["position"] if mapping["position"] is not None else 0,
            created_at=mapping["created_at"],
            updated_at=mapping["updated_at"],
        )
        entries_by_dictionary_id.setdefault(record.resource_data_dictionary_id, []).append(record)

    dictionaries: List[ResourceDataDictionaryRecord] = []
    for row in dictionary_rows:
        mapping = row._mapping
        dictionary_id = mapping["id"]
        dictionaries.append(
            ResourceDataDictionaryRecord(
                id=dictionary_id,
                friendlier_id=mapping["resource_id"],
                name=mapping["name"],
                description=mapping["description"],
                staff_notes=mapping["staff_notes"],
                tags=mapping["tags"] or "",
                position=mapping["position"] if mapping["position"] is not None else 0,
                created_at=mapping["created_at"],
                updated_at=mapping["updated_at"],
                entries=entries_by_dictionary_id.get(dictionary_id, []),
            )
        )

    return dictionaries


def serialize_resource_data_dictionaries(
    dictionaries: List[ResourceDataDictionaryRecord],
) -> List[dict]:
    return [
        {
            "id": item.id,
            "friendlier_id": item.friendlier_id,
            "name": item.name,
            "description": item.description,
            "staff_notes": item.staff_notes,
            "tags": item.tags,
            "position": item.position,
            "created_at": item.created_at,
            "updated_at": item.updated_at,
            "entries": [
                {
                    "id": entry.id,
                    "resource_data_dictionary_id": entry.resource_data_dictionary_id,
                    "friendlier_id": entry.friendlier_id,
                    "field_name": entry.field_name,
                    "field_type": entry.field_type,
                    "values": entry.values,
                    "definition": entry.definition,
                    "definition_source": entry.definition_source,
                    "parent_field_name": entry.parent_field_name,
                    "position": entry.position,
                    "created_at": entry.created_at,
                    "updated_at": entry.updated_at,
                }
                for entry in item.entries
            ],
        }
        for item in dictionaries
    ]
