import asyncio
from dataclasses import replace
from uuid import UUID

import pytest
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import DBAPIError
from test_jobs import MANAGER, setup, submit
from test_managing_sets import api as api
from test_managing_sets import headers

from app.activity import activity
from app.resources.bulk_models import executions, items
from app.resources.models import resources

pytestmark = pytest.mark.integration
BASE = "/api/v1/admin/resource-bulk-actions"
SELECT = "/api/v1/admin/resources/selections"
STAFF = replace(
    MANAGER, permissions=MANAGER.permissions | {"resources:update", "resources:bulk-update"}
)


async def start(api, engine, count=3, query=None):
    client, actor = api
    await setup(api, engine, count)
    actor[0] = STAFF
    selection = await client.post(SELECT, json=query or {}, headers=headers())
    return {
        "selection_id": selection.json()["selection_id"],
        "values": {"schema_provider_s": "Provider", "dct_publisher_sm": ["New", "Second"]},
    }


async def preview(client, payload):
    response = await client.post(BASE, json=payload, headers=headers())
    assert response.status_code == 201, response.text
    return BASE + "/" + response.json()["id"]


async def apply(client, path):
    return await client.put(path + "/confirmation", json={"confirmed": True}, headers=headers())


async def test_bulk_edit_only_changes_checked_matches(api, database_engine):
    client, _ = api
    checked = ["resource-0", "resource-2"]
    payload = await start(api, database_engine, query={"q": "Resource", "ids": checked})
    action = await preview(client, payload)
    assert [row["resource_id"] for row in (await client.get(action)).json()["items"]] == checked
    assert (await apply(client, action)).status_code == 200
    async with database_engine.connect() as conn:
        rows = await conn.execute(
            select(
                resources.c.id, resources.c.schema_provider_s, resources.c.lock_version
            ).order_by(resources.c.id)
        )
        assert rows.all() == [
            ("resource-0", "Provider", 2),
            ("resource-1", None, 1),
            ("resource-2", "Provider", 2),
        ]


async def test_bulk_edit_and_undo_track_exact_values_and_versions(api, database_engine):
    client, actor = api
    payload = await start(api, database_engine, count=262)
    async with database_engine.begin() as conn:
        await conn.execute(
            update(resources).where(resources.c.id == "resource-0").values(dct_publisher_sm=[])
        )
        await conn.execute(
            update(resources).where(resources.c.id == "resource-1").values(**payload["values"])
        )
    key = headers()
    first, replay = await asyncio.gather(
        *[client.post(BASE, json=payload, headers=key) for _ in range(2)]
    )
    assert first.status_code == replay.status_code == 201, first.text
    assert first.json() == replay.json()
    assert (
        await client.post(BASE, json={**payload, "clear_fields": ["dct_format_s"]}, headers=key)
    ).status_code == 409
    path = BASE + "/" + first.json()["id"]
    plan = (await client.get(path, params={"limit": 2})).json()
    assert plan["totals"] == {"ready": 261, "unchanged": 1} and plan["applied_at"] is None
    assert plan["items"][0]["changes"]["dct_publisher_sm"] == {
        "before": [],
        "after": ["New", "Second"],
    }
    assert plan["items"][0]["changes"]["schema_provider_s"]["before"] is None
    assert (
        await client.put(path + "/confirmation", headers=headers(), json={"confirmed": False})
    ).status_code == 422
    async with database_engine.begin() as conn:
        await conn.execute(
            update(resources).where(resources.c.id == "resource-2").values(lock_version=2)
        )
    confirmed = await asyncio.gather(apply(client, path), apply(client, path))
    assert all(r.status_code == 200 for r in confirmed), [r.text for r in confirmed]
    receipt = (await client.get(path)).json()
    assert receipt["totals"] == {"changed": 260, "unchanged": 1, "conflict": 1}
    assert receipt["applied_by"] == STAFF.display_name and receipt["applied_at"]
    assert receipt["items"][0]["after_version"] == 2
    async with database_engine.begin() as conn:
        events = (
            select(func.count())
            .select_from(activity)
            .where(activity.c.correlation_id == UUID(first.json()["id"]))
        )
        assert await conn.scalar(events) == 260
        await conn.execute(
            update(resources)
            .where(resources.c.id == "resource-3")
            .values(lock_version=3, schema_provider_s="Later edit")
        )
    undo = await client.post(path + "/reversions", headers=headers())
    assert undo.status_code == 201, undo.text
    undo_path = BASE + "/" + undo.json()["id"]
    assert (await client.get(undo_path)).json()["totals"] == {"conflict": 1, "ready": 259}
    assert (await apply(client, undo_path)).status_code == 200
    assert (await client.get(undo_path)).json()["reverts"] == first.json()["id"]
    assert (await client.get(BASE)).json()["total"] == 2
    async with database_engine.begin() as conn:
        cols = select(
            resources.c.lock_version, resources.c.dct_publisher_sm, resources.c.schema_provider_s
        )
        assert (await conn.execute(cols.where(resources.c.id == "resource-0"))).one() == (
            3,
            [],
            None,
        )
        assert (await conn.execute(cols.where(resources.c.id == "resource-4"))).one() == (
            3,
            None,
            None,
        )
        assert (
            await conn.scalar(
                select(resources.c.schema_provider_s).where(resources.c.id == "resource-3")
            )
            == "Later edit"
        )
    with pytest.raises(DBAPIError):
        async with database_engine.begin() as conn:
            await conn.execute(update(items).values(changes={}))
    actor[0] = replace(STAFF, set_ids=frozenset())
    assert (await apply(client, path)).status_code == 404
    assert (await client.get(path)).status_code == 404


async def test_bulk_authority_validation_and_atomicity(api, database_engine):
    client, actor = api
    payload = await start(api, database_engine, query={"q": "Resource 1"})
    for change in [
        {"values": {"publication_state": "published"}},
        {"values": {"dct_publisher_sm": "not an array"}},
        {"values": {}},
        {"clear_fields": ["dct_title_s"]},
        {"clear_fields": ["schema_provider_s"]},
    ]:
        assert (
            await client.post(BASE, json={**payload, **change}, headers=headers())
        ).status_code == 422
    path = await preview(client, payload)
    for unprivileged in [MANAGER, replace(STAFF, kind="service_account")]:
        actor[0] = unprivileged
        assert (await apply(client, path)).status_code == 403
    actor[0] = replace(STAFF, actor_id="other")
    assert (await apply(client, path)).status_code == 404
    actor[0] = STAFF
    async with database_engine.begin() as conn:
        await conn.execute(
            text("ALTER TABLE resource_bulk_results ADD CONSTRAINT fail_write CHECK(false)")
        )
    assert (await apply(client, path)).status_code == 503
    async with database_engine.begin() as conn:
        assert await conn.scalar(select(func.count()).select_from(executions)) == 0
        assert await conn.scalar(select(func.max(resources.c.lock_version))) == 1
        await conn.execute(text("ALTER TABLE resource_bulk_results DROP CONSTRAINT fail_write"))
    assert (await apply(client, path)).status_code == 200
    assert (await client.get(path)).json()["totals"] == {"changed": 1}


async def test_bulk_clear_unassigned_draft_and_skip_protected_resources(api, database_engine):
    client, actor = api
    job, _ = await setup(api, database_engine, 3)
    actor[0] = STAFF
    async with database_engine.begin() as conn:
        await conn.execute(update(resources).values(dct_accessRights_s="Legacy value"))
        await conn.execute(
            update(resources).where(resources.c.id == "resource-0").values(set_id=None)
        )
        await conn.execute(
            update(resources)
            .where(resources.c.id == "resource-1")
            .values(publication_state="published")
        )
    saved = (await client.post(SELECT, json={}, headers=headers())).json()
    assert saved["total"] == 3
    path = await preview(
        client,
        {
            "selection_id": saved["selection_id"],
            "clear_fields": ["dct_accessRights_s"],
        },
    )
    assert (await client.get(path)).json()["totals"] == {"ready": 2, "read_only": 1}
    await submit(client, {**job, "selection": job["selection"][2:]})
    assert (await apply(client, path)).status_code == 200
    report = (await client.get(path)).json()
    assert report["totals"] == {"changed": 1, "read_only": 1, "active_job": 1}
    assert report["items"][0]["changes"]["dct_accessRights_s"] == {
        "before": "Legacy value",
        "after": None,
    }
    undo = (await client.post(path + "/reversions", headers=headers())).json()
    assert (await apply(client, BASE + "/" + undo["id"])).status_code == 200
    async with database_engine.connect() as conn:
        assert (
            await conn.execute(
                select(resources.c.lock_version, resources.c.dct_accessRights_s).where(
                    resources.c.id == "resource-0"
                )
            )
        ).one() == (3, "Legacy value")
