"""A Resource inherits Source identity from its one managing Set."""

import csv
import io
import json
from dataclasses import replace
from uuid import uuid4

import pytest
import test_resources
from alembic import command
from conftest import alembic_config
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import DBAPIError
from test_managing_sets import create, headers
from test_resource_csv import document
from test_resource_csv import preview as csv_preview
from test_resource_editor import patch, seed
from test_resources import BASE, preview

from app.activity import activity
from app.resources.models import evidence, resources
from app.sets.models import commands
from app.url_ids import encode_id

api = test_resources.api
pytestmark = pytest.mark.integration


async def setup(api):
    client, actor, scope, record = await seed(api)
    actor[0] = replace(
        actor[0],
        permissions=actor[0].permissions
        | {
            "sources:read",
            "sources:use",
            "sources:create",
            "resources:associate",
        },
    )
    for identifier in ["Source_A", "Source-B"]:
        response = await client.post(
            "/api/v1/admin/sources",
            headers=headers(),
            json={
                "source_id": identifier,
                "title": identifier,
                "admin_notes": "Private source note",
            },
        )
        assert response.status_code == 201, response.text
    return client, actor, scope, record


async def test_source_is_derived_and_cannot_be_edited_or_cleared(api, database_engine):
    client, _, _, record = await setup(api)
    # Historical evidence must not override the current managing Set's Source.
    async with database_engine.begin() as connection:
        await connection.execute(update(resources).values(legacy_source_id="Source_A"))
    detail = (await client.get(BASE + "/" + encode_id(record["id"]))).json()
    assert detail["source_id"] == "parent"
    assert not {"source_id", "legacy_source_id", "lifecycle_id"} & detail["metadata"].keys()
    for body in [
        {"values": {"source_id": "Source_A"}},
        {"values": {"source_id": "parent"}},
        {"values": {"legacy_source_id": "Source_A"}},
        {"clear_fields": ["source_id"]},
    ]:
        response = await patch(client, {"lock_version": 1, **body})
        assert response.status_code == 422
        assert response.json()["detail"]["code"] == "invalid_fields"
    assert (await client.get(BASE + "/" + encode_id(record["id"]))).json()["lock_version"] == 1


async def test_json_assertions_use_set_source_preserve_evidence_and_recheck_access(
    api, database_engine
):
    client, actors, scope, _ = await setup(api)
    actors[0] = replace(actors[0], permissions=actors[0].permissions - {"sources:use"})
    records = [
        {
            "id": "asserted",
            "dct_title_s": "Asserted",
            "source_id": "parent",
            "dct_source_sm": ["Provenance"],
        },
        {"id": "derived", "dct_title_s": "Derived", "legacy_source_id": "Source_A"},
        *[
            {"id": f"bad-{i}", "dct_title_s": "Mismatch", "source_id": value}
            for i, value in enumerate(["Source_A", "missing", "", None, [], {}])
        ],
    ]
    body, plan = await preview(client, scope, records)
    assert plan["ready"] == 2
    assert all("managing Set" in row["errors"][0] for row in plan["items"][2:])
    key = uuid4()
    response = await client.post(BASE + "/imports", headers=headers(key), json=body)
    assert response.json()["created"] == 2
    assert (
        await client.post(BASE + "/imports", headers=headers(key), json=body)
    ).json() == response.json()
    detail = (await client.get(BASE + "/asserted")).json()
    assert detail["source_id"] == "parent"
    assert detail["metadata"]["dct_source_sm"] == ["Provenance"]
    async with database_engine.connect() as connection:
        assert (
            await connection.scalar(
                select(evidence.c.source_record).where(evidence.c.resource_id == "asserted")
            )
            == records[0]
        )
        assert (
            await connection.scalar(
                select(resources.c.legacy_source_id).where(resources.c.id == "derived")
            )
            is None
        )
    actors[0] = replace(actors[0], set_ids=frozenset())
    assert (
        await client.post(BASE + "/imports", headers=headers(key), json=body)
    ).status_code == 404


@pytest.mark.parametrize(
    "format,source_header", [("technical", "source_id"), ("geomg", "Source ID")]
)
async def test_csv_round_trip_assertions_and_invalid_clears(api, format, source_header):
    client, actors, scope, _ = await setup(api)
    actors[0] = replace(actors[0], permissions=actors[0].permissions - {"sources:use"})
    body, plan = await csv_preview(
        client,
        scope,
        document(["id", "dct_title_s", source_header], ["csv-resource", "CSV", "parent"]),
        "create",
    )
    assert plan["ready"] == 1
    key = uuid4()
    result = await client.post(BASE + "/csv/import", headers=headers(key), json=body)
    assert result.json()["items"][0]["outcome"] == "created"
    assert (
        await client.post(BASE + "/csv/import", headers=headers(key), json=body)
    ).json() == result.json()
    exported = await client.get(
        BASE + "/csv/export", params={"format": format, "ids": ["csv-resource"]}
    )
    rows = list(csv.DictReader(io.StringIO(exported.text)))
    assert rows[0][source_header] == "parent"
    assert source_header + "__clear" not in rows[0]
    _, round_trip = await csv_preview(client, scope, exported.text)
    assert round_trip["items"][0]["outcome"] == "unchanged"
    assert "source_id" not in round_trip["items"][0]["changes"]
    for value, clear in [("Source_A", ""), ("", "true"), ("parent", "true"), (" ", "")]:
        _, invalid = await csv_preview(
            client,
            scope,
            document(
                ["id", "lock_version", source_header, source_header + "__clear"],
                ["csv-resource", "1", value, clear],
            ),
        )
        assert invalid["ready"] == 0 and invalid["items"][0]["outcome"] == "invalid"
    body, plan = await csv_preview(
        client,
        scope,
        document(
            ["id", "lock_version", source_header, "dct_title_s"],
            ["csv-resource", "1", "", "Changed"],
        ),
    )
    assert plan["ready"] == 1 and set(plan["items"][0]["changes"]) == {"dct_title_s"}
    assert (
        await client.post(BASE + "/csv/import", headers=headers(), json=body)
    ).status_code == 200
    assert (await client.get(BASE + "/csv-resource")).json()["source_id"] == "parent"


async def test_one_source_many_sets_keep_separate_scope_and_shared_source_filter(api):
    client, actors, origin, _ = await setup(api)
    sibling = await create(client, set_id="sibling", source_id="parent")
    hidden = await create(client, set_id="hidden", source_id="parent")
    other = await create(client, set_id="other", source_id="Source_A")
    for scope in [sibling, hidden, other]:
        body, _ = await preview(
            client, scope, [{"id": scope["set_id"], "dct_title_s": scope["title"]}]
        )
        assert (await client.post(BASE + "/imports", headers=headers(), json=body)).json()[
            "created"
        ] == 1
    actors[0] = replace(
        actors[0], set_ids=frozenset({origin["set_id"], sibling["set_id"], other["set_id"]})
    )
    for filters, expected in [
        ({"source": ["parent"]}, {"editor/test", "sibling"}),
        ({"source": [""]}, set()),
        ({"source": {"exclude": ["parent"]}}, {"other"}),
        ({"set": ["sibling"]}, {"sibling"}),
    ]:
        params = {"filters": json.dumps(filters)}
        page = (await client.get(BASE, params=params)).json()
        assert {row["id"] for row in page["items"]} == expected
        exported = await client.get(BASE + "/csv/export", params=params)
        assert {row["id"] for row in csv.DictReader(io.StringIO(exported.text))} == expected
        selected = await client.post(
            BASE + "/selections", headers=headers(), json={"filters": filters}
        )
        assert selected.status_code == 201 and selected.json()["total"] == len(expected)
        facet = (await client.get(BASE + "/facets/publication", params=params)).json()
        assert sum(row["count"] for row in facet["items"]) == len(expected)
    facet = (await client.get(BASE + "/facets/source")).json()
    assert {row["value"]: row["count"] for row in facet["items"]} == {"parent": 2, "Source_A": 1}
    assert "Private source note" not in str(facet)
    assert (await client.get(f"/api/v1/admin/sets/{origin['set_id']}")).json()[
        "resource_count"
    ] == 1
    assert (await client.get("/api/v1/admin/sets/sibling")).json()["resource_count"] == 1


async def test_cross_source_set_move_is_atomic_and_invalidates_old_csv_preview(
    api, database_engine
):
    client, _, origin, record = await setup(api)
    target = await create(client, source_id="Source_A")
    payload, _ = await csv_preview(
        client,
        origin,
        document(
            ["id", "lock_version", "source_id", "dct_title_s"],
            [record["id"], "1", "parent", "Stale"],
        ),
    )
    body = {
        "source_set_id": origin["set_id"],
        "target_set_id": target["set_id"],
        "resource_version": 1,
        "reason": "Reviewed reassignment",
        "confirmed": True,
    }
    path = BASE + "/" + encode_id(record["id"]) + "/set"
    async with database_engine.begin() as connection:
        before = await connection.scalar(select(func.count()).select_from(activity))
        receipts = await connection.scalar(select(func.count()).select_from(commands))
        await connection.execute(
            text("""CREATE FUNCTION reject_association() RETURNS trigger
            LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'private failure'; END $$""")
        )
        await connection.execute(
            text(
                "CREATE TRIGGER reject_association BEFORE INSERT ON lifecycle_activity_entries "
                "FOR EACH ROW EXECUTE FUNCTION reject_association()"
            )
        )
    key = uuid4()
    assert (await client.put(path, headers=headers(key), json=body)).status_code == 503
    async with database_engine.begin() as connection:
        assert await connection.scalar(select(resources.c.set_id)) == origin["set_id"]
        assert await connection.scalar(select(func.count()).select_from(activity)) == before
        assert await connection.scalar(select(func.count()).select_from(commands)) == receipts
        await connection.execute(
            text("DROP TRIGGER reject_association ON lifecycle_activity_entries")
        )
    saved = await client.put(path, headers=headers(key), json=body)
    assert saved.status_code == 200 and saved.json()["source_id"] == "Source_A"
    assert (await client.put(path, headers=headers(key), json=body)).json() == saved.json()
    detail = (await client.get(BASE + "/" + encode_id(record["id"]))).json()
    assert detail["source_id"] == "Source_A" and detail["lock_version"] == 2
    assert detail["metadata"]["dct_title_s"] == record["dct_title_s"]
    assert (
        await client.post(BASE + "/csv/import", headers=headers(), json=payload)
    ).status_code == 409
    async with database_engine.connect() as connection:
        events = (
            (
                await connection.execute(
                    select(activity.c.details).where(activity.c.action == "resource.associated")
                )
            )
            .scalars()
            .all()
        )
        assert len(events) == 2
        assert all(
            e["previous_source_id"] == "parent" and e["source_id"] == "Source_A" for e in events
        )
        assert await connection.scalar(select(evidence.c.source_record)) == record


async def test_bridge_keeps_upstream_source_only_in_evidence(api):
    client, _, scope, _ = await setup(api)
    record = {"id": "bridge-source", "dct_title_s": "Bridge", "source_id": "Source_A"}
    result = await client.post(
        BASE + "/bridge/batches",
        headers=headers(),
        json={"set_id": scope["set_id"], "records": [record]},
    )
    assert result.status_code == 200 and result.json()["created"] == 1
    detail = (await client.get(BASE + "/bridge-source")).json()
    assert detail["source_id"] == "parent" and detail["source_record"] == record


async def test_legacy_migration_preserves_reviewed_source_evidence(database_engine):
    from legacy_data import lifecycle

    async with database_engine.begin() as connection:
        await connection.run_sync(lambda sync: command.downgrade(alembic_config(sync), "0014"))
        await lifecycle(connection, resource_id="legacy-map")
        await connection.run_sync(lambda sync: command.upgrade(alembic_config(sync), "0021"))
        assert await connection.scalar(text("SELECT source_id FROM resources")) is None
    with pytest.raises(DBAPIError):
        async with database_engine.begin() as connection:
            await connection.execute(text("UPDATE resources SET source_id = 'missing'"))
    async with database_engine.begin() as connection:
        await connection.execute(
            text("""INSERT INTO sources (source_id, title, created_by_actor_id, updated_by_actor_id)
            SELECT 'ReviewedSource', 'Reviewed Source', id, id FROM actors LIMIT 1""")
        )
        await connection.execute(text("UPDATE resources SET source_id = 'ReviewedSource'"))
    with pytest.raises(DBAPIError, match="Cannot discard Resource Source"):
        async with database_engine.begin() as connection:
            await connection.run_sync(lambda sync: command.downgrade(alembic_config(sync), "0014"))
