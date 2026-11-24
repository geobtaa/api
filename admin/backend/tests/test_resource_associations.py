from dataclasses import replace

import pytest
import test_resources
from alembic import command
from conftest import alembic_config
from sqlalchemy import delete, func, insert, inspect, select
from sqlalchemy.exc import IntegrityError
from test_resource_editor import seed
from test_resources import BASE

from app.resources.association_models import (
    FAMILIES,
    resource_assets,
    resource_data_dictionaries,
    resource_data_dictionary_entries,
    resource_downloads,
    resource_licensed_accesses,
    resource_relationships,
)
from app.resources.models import resources
from app.url_ids import encode_id

api = test_resources.api
pytestmark = pytest.mark.integration


async def test_all_association_families_scoped_typed_and_paginated(api, database_engine):
    client, actors, _, _ = await seed(api)
    async with database_engine.begin() as connection:
        await connection.execute(
            insert(resource_relationships),
            [
                {
                    "subject_id": "editor/test",
                    "predicate": "dct_isPartOf_sm",
                    "object_id": "external/missing",
                },
                {
                    "subject_id": "unmanaged",
                    "predicate": "dct_relation_sm",
                    "object_id": "editor/test",
                },
            ],
        )
        await connection.execute(
            insert(resource_downloads),
            [
                {
                    "resource_id": "editor/test",
                    "label": "Second",
                    "value": "legacy value",
                    "position": 2,
                },
                {
                    "resource_id": "editor/test",
                    "label": "First",
                    "value": "https://example.org/file",
                    "position": 1,
                },
            ],
        )
        await connection.execute(
            insert(resource_licensed_accesses).values(
                resource_id="editor/test",
                institution_code="TEST",
                access_url="https://example.org/licensed",
            )
        )
        await connection.execute(
            insert(resource_assets).values(
                resource_id="editor/test",
                title="Scan",
                file_url="https://example.org/image",
                file_width=1200,
                file_height=800,
                file_size=0,
                thumbnail=False,
                file_sha512="a" * 128,
            )
        )
        dictionary = await connection.scalar(
            insert(resource_data_dictionaries)
            .values(
                resource_id="editor/test",
                name="Parcels",
                staff_notes="Internal note",
                tags="legacy|tags",
            )
            .returning(resource_data_dictionaries.c.id)
        )
        await connection.execute(
            insert(resource_data_dictionary_entries).values(
                resource_data_dictionary_id=dictionary,
                field_name="parcel_id",
                field_type="text",
                definition="Parcel identifier",
                values="001|002",
            )
        )
    for family in FAMILIES:
        response = await client.get(
            BASE + "/" + encode_id("editor/test") + "/associations/" + family, params={"limit": 1}
        )
        assert response.status_code == 200, response.text
        assert response.headers["cache-control"] == "no-store"
        page = response.json()
        assert len(page["items"]) == 1
        assert page["total"] == (2 if family == "downloads" else 1)
        item = page["items"][0]
        if family == "relationships":
            assert item["object_id"] == "external/missing"
        if family == "downloads":
            assert item["label"] == "First"
        if family == "assets":
            assert item["file_size"] == 0 and item["thumbnail"] is False
        if family == "data-dictionaries":
            assert item["staff_notes"] == "Internal note"
        if family == "dictionary-entries":
            assert item["values"] == "001|002"
    second = (
        await client.get(
            BASE + "/" + encode_id("editor/test") + "/associations/downloads",
            params={"offset": 1, "limit": 1},
        )
    ).json()
    assert second["items"][0]["label"] == "Second"
    for params in [{"id": "editor/test", "limit": 101}, {"id": "editor/test", "offset": -1}]:
        assert (
            await client.get(
                BASE + "/" + encode_id(params["id"]) + "/associations/assets",
                params={key: value for key, value in params.items() if key != "id"},
            )
        ).status_code == 422
    assert (
        await client.get(BASE + "/" + encode_id("editor/test") + "/associations/unknown", params={})
    ).status_code == 422
    assert (
        await client.get(BASE + "/" + encode_id("missing") + "/associations/assets", params={})
    ).status_code == 404
    actors[0] = replace(actors[0], set_ids=frozenset())
    for family in FAMILIES:
        assert (
            await client.get(
                BASE + "/" + encode_id("editor/test") + "/associations/" + family, params={}
            )
        ).status_code == 404
    actors[0] = replace(actors[0], set_ids=None, kind="service_account")
    assert (
        await client.get(BASE + "/" + encode_id("editor/test") + "/associations/assets", params={})
    ).status_code == 403
    actors[0] = replace(actors[0], kind="user", permissions=frozenset({"resources:read"}))
    assert (
        await client.get(
            BASE + "/" + encode_id("editor/test") + "/associations/licensed-accesses", params={}
        )
    ).status_code == 403
    assert (
        await client.get(
            BASE + "/" + encode_id("editor/test") + "/associations/data-dictionaries", params={}
        )
    ).status_code == 403


async def test_dictionary_integrity_and_transaction_rollback(database_engine):
    async with database_engine.begin() as connection:
        dictionary = await connection.scalar(
            insert(resource_data_dictionaries)
            .values(resource_id="external")
            .returning(resource_data_dictionaries.c.id)
        )
        await connection.execute(
            insert(resource_data_dictionary_entries).values(
                resource_data_dictionary_id=dictionary,
                field_name="code",
                parent_field_name="parent",
                position=0,
            )
        )
    with pytest.raises(IntegrityError):
        async with database_engine.begin() as connection:
            await connection.execute(insert(resource_downloads).values(resource_id="external"))
            await connection.execute(
                insert(resource_data_dictionary_entries).values(
                    resource_data_dictionary_id=dictionary,
                    field_name="code",
                    parent_field_name="parent",
                    position=0,
                )
            )
    async with database_engine.begin() as connection:
        assert await connection.scalar(select(func.count()).select_from(resource_downloads)) == 0
        await connection.execute(
            delete(resource_data_dictionaries).where(resource_data_dictionaries.c.id == dictionary)
        )
        assert (
            await connection.scalar(
                select(func.count()).select_from(resource_data_dictionary_entries)
            )
            == 0
        )
    with pytest.raises(IntegrityError):
        async with database_engine.begin() as connection:
            await connection.execute(
                insert(resource_data_dictionary_entries).values(
                    resource_data_dictionary_id=dictionary, field_name="bad"
                )
            )


async def test_migration_roundtrip_preserves_existing_resources(database_engine):
    from legacy_data import lifecycle

    async with database_engine.begin() as connection:
        await connection.run_sync(lambda sync: command.downgrade(alembic_config(sync), "0003"))
        await lifecycle(connection, resource_id="legacy-map")

        def migrate(sync):
            assert "resource_assets" not in inspect(sync).get_table_names()
            command.upgrade(alembic_config(sync), "0021")
            for table in FAMILIES.values():
                assert table.name in inspect(sync).get_table_names()
                if table.name != "resource_data_dictionary_entries":
                    assert inspect(sync).get_foreign_keys(table.name) == []

        await connection.run_sync(migrate)
        assert await connection.scalar(select(func.count()).select_from(resources)) == 1
