from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import document_data_dictionaries, document_data_dictionary_entries


@dataclass(frozen=True)
class DocumentDataDictionaryEntryRecord:
    id: int
    document_data_dictionary_id: int
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
class DocumentDataDictionaryRecord:
    id: int
    friendlier_id: str
    name: Optional[str]
    description: Optional[str]
    staff_notes: Optional[str]
    tags: str
    position: int
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    entries: List[DocumentDataDictionaryEntryRecord]


async def fetch_document_data_dictionaries(
    resource_id: str, *, session: AsyncSession
) -> List[DocumentDataDictionaryRecord]:
    """Fetch dictionaries and entries for a resource, ordered by position."""
    dictionaries_stmt = (
        select(document_data_dictionaries)
        .where(document_data_dictionaries.c.friendlier_id == resource_id)
        .order_by(
            document_data_dictionaries.c.position,
            document_data_dictionaries.c.id,
        )
    )
    dictionaries_result = await session.execute(dictionaries_stmt)
    dictionary_rows = dictionaries_result.fetchall()

    if not dictionary_rows:
        return []

    dictionary_ids = [row._mapping["id"] for row in dictionary_rows]

    entries_stmt = (
        select(document_data_dictionary_entries)
        .where(document_data_dictionary_entries.c.document_data_dictionary_id.in_(dictionary_ids))
        .order_by(
            document_data_dictionary_entries.c.document_data_dictionary_id,
            document_data_dictionary_entries.c.position,
            document_data_dictionary_entries.c.id,
        )
    )
    entries_result = await session.execute(entries_stmt)
    entries_rows = entries_result.fetchall()

    entries_by_dictionary_id: Dict[int, List[DocumentDataDictionaryEntryRecord]] = {}
    for row in entries_rows:
        mapping = row._mapping
        record = DocumentDataDictionaryEntryRecord(
            id=mapping["id"],
            document_data_dictionary_id=mapping["document_data_dictionary_id"],
            friendlier_id=mapping["friendlier_id"],
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
        entries_by_dictionary_id.setdefault(record.document_data_dictionary_id, []).append(record)

    dictionaries: List[DocumentDataDictionaryRecord] = []
    for row in dictionary_rows:
        mapping = row._mapping
        dictionary_id = mapping["id"]
        dictionaries.append(
            DocumentDataDictionaryRecord(
                id=dictionary_id,
                friendlier_id=mapping["friendlier_id"],
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


def serialize_document_data_dictionaries(
    dictionaries: List[DocumentDataDictionaryRecord],
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
                    "document_data_dictionary_id": entry.document_data_dictionary_id,
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
