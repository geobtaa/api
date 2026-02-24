from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.data_dictionary_repository import (
    fetch_resource_data_dictionaries,
    serialize_resource_data_dictionaries,
)


def _row(mapping: dict):
    row = MagicMock()
    row._mapping = mapping
    return row


@pytest.mark.unit
@pytest.mark.asyncio
async def test_fetch_resource_data_dictionaries_prefers_resource_tables():
    session = AsyncMock()

    dictionary_rows = [
        _row(
            {
                "id": 11,
                "resource_id": "resource-1",
                "name": "Attributes",
                "description": "Dictionary description",
                "staff_notes": "Internal note",
                "tags": "tag1,tag2",
                "position": 1,
                "created_at": None,
                "updated_at": None,
            }
        )
    ]
    entry_rows = [
        _row(
            {
                "id": 101,
                "resource_data_dictionary_id": 11,
                "field_name": "parcel_id",
                "field_type": "string",
                "values": None,
                "definition": "Parcel identifier",
                "definition_source": "County schema",
                "parent_field_name": None,
                "position": 1,
                "created_at": None,
                "updated_at": None,
            }
        )
    ]

    session.execute.side_effect = [
        SimpleNamespace(fetchall=lambda: dictionary_rows),
        SimpleNamespace(fetchall=lambda: entry_rows),
    ]

    dictionaries = await fetch_resource_data_dictionaries("resource-1", session=session)

    assert len(dictionaries) == 1
    dictionary = dictionaries[0]
    assert dictionary.id == 11
    assert dictionary.friendlier_id == "resource-1"
    assert dictionary.name == "Attributes"
    assert len(dictionary.entries) == 1
    assert dictionary.entries[0].resource_data_dictionary_id == 11
    assert dictionary.entries[0].friendlier_id == "resource-1"
    assert dictionary.entries[0].field_name == "parcel_id"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_fetch_resource_data_dictionaries_falls_back_to_legacy_tables():
    session = AsyncMock()

    legacy_dictionary_rows = [
        _row(
            {
                "id": 21,
                "friendlier_id": "resource-legacy",
                "name": "Legacy Attributes",
                "description": None,
                "staff_notes": None,
                "tags": "",
                "position": 0,
                "created_at": None,
                "updated_at": None,
            }
        )
    ]
    legacy_entry_rows = [
        _row(
            {
                "id": 201,
                "document_data_dictionary_id": 21,
                "field_name": "legacy_field",
                "field_type": "integer",
                "values": "1,2,3",
                "definition": "Legacy definition",
                "definition_source": None,
                "parent_field_name": None,
                "position": 0,
                "created_at": None,
                "updated_at": None,
            }
        )
    ]

    session.execute.side_effect = [
        Exception("resource tables not present"),
        SimpleNamespace(fetchall=lambda: legacy_dictionary_rows),
        SimpleNamespace(fetchall=lambda: legacy_entry_rows),
    ]

    dictionaries = await fetch_resource_data_dictionaries("resource-legacy", session=session)

    assert len(dictionaries) == 1
    dictionary = dictionaries[0]
    assert dictionary.id == 21
    assert dictionary.friendlier_id == "resource-legacy"
    assert dictionary.name == "Legacy Attributes"
    assert len(dictionary.entries) == 1
    assert dictionary.entries[0].resource_data_dictionary_id == 21
    assert dictionary.entries[0].friendlier_id == "resource-legacy"
    assert dictionary.entries[0].field_name == "legacy_field"


@pytest.mark.unit
def test_serialize_resource_data_dictionaries_uses_resource_key_name():
    dictionary = SimpleNamespace(
        id=1,
        friendlier_id="resource-1",
        name="Attributes",
        description=None,
        staff_notes=None,
        tags="",
        position=0,
        created_at=None,
        updated_at=None,
        entries=[
            SimpleNamespace(
                id=10,
                resource_data_dictionary_id=1,
                friendlier_id="resource-1",
                field_name="parcel_id",
                field_type="string",
                values=None,
                definition=None,
                definition_source=None,
                parent_field_name=None,
                position=0,
                created_at=None,
                updated_at=None,
            )
        ],
    )

    payload = serialize_resource_data_dictionaries([dictionary])

    assert len(payload) == 1
    assert payload[0]["entries"][0]["resource_data_dictionary_id"] == 1
    assert "document_data_dictionary_id" not in payload[0]["entries"][0]
