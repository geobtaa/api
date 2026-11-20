import asyncio
from dataclasses import replace
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, insert, select, text
from sqlalchemy.exc import DBAPIError
from test_managing_sets import EDITOR, create, headers
from test_managing_sets import api as set_api

from app.activity import activity
from app.sets.models import commands
from app.workflows.models import versions
from app.workflows.schemas import PROCESS_TYPES

api = set_api
pytestmark = pytest.mark.integration
BASE = "/api/v1/admin/workflows"
MANAGER = replace(
    EDITOR,
    permissions=EDITOR.permissions
    | {"workflows:read", "workflows:change", "workflows:activate", "sets:retire"},
)


def process(position=1, kind="review", **config):
    return {"position": position, "process_type": kind, "name": kind, "configuration": config}


async def setup_workflow(api, entries=None):
    client, actor = api
    actor[0] = MANAGER
    scope = await create(client)
    body = {
        "set_id": scope["set_id"],
        "title": "County workflow",
        "processes": entries if entries is not None else [process()],
    }
    response = await client.post(BASE, headers=headers(), json=body)
    assert response.status_code == 201, response.text
    return response.json(), body


async def activate(client, item, key=None):
    return await client.post(
        BASE + "/" + item["workflow_id"] + "/activate",
        headers=headers(key),
        json={
            "lock_version": item["lock_version"],
            "version_id": item["draft"]["version_id"],
            "confirmed": True,
        },
    )


async def test_workflow_versions_history_pinned_definition_and_activity(api, database_engine):
    client, _ = api
    item, body = await setup_workflow(
        api,
        [process(1, "template_csv", template_ref="county/v1"), process(2, "validate"), process(3)],
    )
    contract = (await client.get("/api/v1/admin/contracts/workflows")).json()
    assert {
        r["key"]: (r["label"], r["definition"]) for r in contract["process_types"]
    } == PROCESS_TYPES
    assert contract["can_create"] is True
    assert "additionalProperties" in contract["configuration_schema"]
    for title in ["Second", "Third"]:
        assert (
            await client.post(BASE, headers=headers(), json={**body, "title": title})
        ).status_code == 201
    page = (
        await client.get(BASE, params={"set_id": body["set_id"], "offset": 1, "limit": 1})
    ).json()
    assert page["total"] == 3 and len(page["items"]) == 1
    path = BASE + "/" + item["workflow_id"]
    result = await activate(client, item)
    assert result.status_code == 200, result.text
    item = result.json()
    original = item["active"]
    assert len(original["checksum"]) == 64
    cloned = await client.post(path + "/draft", headers=headers(), json={"lock_version": 2})
    assert cloned.status_code == 200, cloned.text
    item = cloned.json()
    assert item["draft"]["processes"] == original["processes"]
    assert item["draft"]["number"] == 2
    updated = await client.put(
        path + "/draft",
        headers=headers(),
        json={
            "lock_version": 3,
            "processes": [
                process(
                    1,
                    "harvest",
                    endpoint_url="https://example.org/catalog",
                    credential_ref="county/read",
                ),
                process(2, "review"),
            ],
        },
    )
    assert updated.status_code == 200, updated.text
    item = updated.json()
    assert item["active"] == original
    result = await activate(client, item)
    assert result.status_code == 200, result.text
    history = (await client.get(path + "/versions", params={"offset": 1, "limit": 1})).json()
    assert history["total"] == 2
    pinned = history["items"][0]
    assert pinned == {**original, "state": "superseded"}
    assert (await client.get(path + "/versions/" + original["version_id"])).json() == pinned
    assert (await client.get(path + "/versions/" + str(uuid4()))).status_code == 404
    assert (await client.get(path)).json()["active"]["number"] == 2
    async with database_engine.connect() as connection:
        rows = (
            (
                await connection.execute(
                    select(activity)
                    .where(activity.c.workflow_id == UUID(item["workflow_id"]))
                    .order_by(activity.c.occurred_at)
                )
            )
            .mappings()
            .all()
        )
        assert [r["action"] for r in rows] == [
            "workflow.created",
            "workflow.activated",
            "workflow.draft_created",
            "workflow.updated",
            "workflow.activated",
        ]
        assert all(r["workflow_version_id"] is not None for r in rows)


async def test_concurrent_activation_idempotency_stale_and_permissions(api):
    client, actor = api
    item, body = await setup_workflow(api)
    key = uuid4()
    results = await asyncio.gather(activate(client, item, key), activate(client, item, key))
    assert [r.status_code for r in results] == [200, 200]
    assert results[0].json() == results[1].json()
    assert (await activate(client, item)).status_code == 409
    path = BASE + "/" + item["workflow_id"]
    actor[0] = replace(MANAGER, permissions=MANAGER.permissions - {"workflows:activate"})
    assert (await activate(client, item, key)).status_code == 403
    actor[0] = replace(MANAGER, kind="service_account")
    assert (await client.get(path)).status_code == 200
    assert (await client.post(BASE, headers=headers(), json=body)).status_code == 403
    actor[0] = replace(MANAGER, set_ids=frozenset())
    assert (await client.get(path)).status_code == 404
    assert (await client.get(path + "/versions")).status_code == 404
    assert (await client.get(BASE, params={"set_id": body["set_id"]})).status_code == 404
    assert (await activate(client, item, key)).status_code == 404
    actor[0] = EDITOR
    assert (await client.get(path)).status_code == 403
    actor[0] = None
    assert (await client.get(path)).status_code == 401


async def test_draft_validation_and_empty_activation_do_not_change_active(api):
    client, _ = api
    item, _ = await setup_workflow(api)
    path = BASE + "/" + item["workflow_id"]
    for entries in [
        [process(2)],
        [process(), process()],
        [process(kind="unknown")],
        [process(kind="harvest", password="secret")],
        [process(kind="harvest", endpoint_url="https://u:p@example.org")],
        [process(kind="harvest", endpoint_url="https://example.org?token=secret")],
        [process(kind="harvest", credential_ref="Bearer SECRET")],
        [process(kind="review", mapping_ref="mapping")],
        [{**process(), "configuration_schema_version": 2}],
    ]:
        assert (
            await client.put(
                path + "/draft", headers=headers(), json={"lock_version": 1, "processes": entries}
            )
        ).status_code == 422
    active = (await activate(client, item)).json()["active"]
    assert (
        await client.put(
            path + "/draft", headers=headers(), json={"lock_version": 2, "processes": []}
        )
    ).status_code == 409
    item = (await client.post(path + "/draft", headers=headers(), json={"lock_version": 2})).json()
    assert (
        await client.post(path + "/draft", headers=headers(), json={"lock_version": 3})
    ).status_code == 409
    item = (
        await client.put(
            path + "/draft", headers=headers(), json={"lock_version": 3, "processes": []}
        )
    ).json()
    assert (await activate(client, item)).status_code == 422
    assert (await client.get(path)).json()["active"] == active
    assert (
        await client.post(
            path + "/activate",
            headers=headers(),
            json={"lock_version": 4, "version_id": str(uuid4()), "confirmed": True},
        )
    ).status_code == 409
    assert (
        await client.post(
            path + "/activate",
            headers=headers(),
            json={"lock_version": 4, "version_id": item["draft"]["version_id"], "confirmed": False},
        )
    ).status_code == 422


async def test_database_guards_preserve_activated_definitions(api, database_engine):
    client, _ = api
    item, _ = await setup_workflow(api)
    item = (await activate(client, item)).json()
    for sql in [
        "UPDATE workflow_processes SET name = 'changed'",
        "DELETE FROM workflow_processes",
        "UPDATE workflow_versions SET checksum = repeat('a', 64)",
        "DELETE FROM workflow_versions",
        "UPDATE workflows SET set_id = gen_random_uuid()",
    ]:
        with pytest.raises(DBAPIError):
            async with database_engine.begin() as connection:
                await connection.execute(text(sql))
    path = BASE + "/" + item["workflow_id"]
    draft = (await client.post(path + "/draft", headers=headers(), json={"lock_version": 2})).json()
    for sql in [
        "UPDATE workflow_versions SET number = 7 WHERE state = 'draft'",
        "UPDATE workflow_versions SET state = 'superseded' WHERE state = 'draft'",
        "UPDATE workflow_processes SET version_id = "
        "(SELECT version_id FROM workflow_versions WHERE state = 'draft') "
        "WHERE version_id = (SELECT version_id FROM workflow_versions WHERE state = 'active')",
    ]:
        with pytest.raises(DBAPIError):
            async with database_engine.begin() as connection:
                await connection.execute(text(sql))
    assert (await activate(client, draft)).status_code == 200
    with pytest.raises(DBAPIError):
        async with database_engine.begin() as connection:
            await connection.execute(
                text("UPDATE workflow_versions SET state = 'active' WHERE state = 'superseded'")
            )


async def test_atomic_activity_failure_and_retirement(api, database_engine):
    client, actor = api
    item, body = await setup_workflow(api)
    async with database_engine.begin() as connection:
        await connection.execute(
            text("""CREATE FUNCTION reject_workflow_activity() RETURNS trigger
            LANGUAGE plpgsql AS $$
            BEGIN RAISE EXCEPTION 'private failure'; END $$""")
        )
        await connection.execute(
            text("""CREATE TRIGGER reject_workflow BEFORE INSERT ON lifecycle_activity_entries
            FOR EACH ROW EXECUTE FUNCTION reject_workflow_activity()""")
        )
    key = uuid4()
    assert (await activate(client, item, key)).status_code == 503
    async with database_engine.begin() as connection:
        assert await connection.scalar(select(versions.c.state)) == "draft"
        assert await connection.scalar(select(func.count()).select_from(commands)) == 2
        await connection.execute(text("DROP TRIGGER reject_workflow ON lifecycle_activity_entries"))
    assert (await activate(client, item, key)).status_code == 200
    retired = await client.put(
        "/api/v1/admin/sets/" + body["set_id"] + "/state",
        headers=headers(),
        json={"target": "retired", "reason": "Closed", "confirmed": True, "lock_version": 1},
    )
    assert retired.status_code == 200
    assert (await client.post(BASE, headers=headers(), json=body)).status_code == 409
    assert (await client.get(BASE + "/" + item["workflow_id"])).json()["can_change"] is False


async def test_create_receipt_conflict_and_concurrent_distinct_activation(api):
    client, actor = api
    actor[0] = MANAGER
    scope = await create(client)
    body = {
        "set_id": scope["set_id"],
        "title": "Workflow",
        "processes": [process()],
    }
    key = headers()
    created = await asyncio.gather(*[client.post(BASE, headers=key, json=body) for _ in range(2)])
    assert all(r.status_code == 201 for r in created)
    assert created[0].json() == created[1].json()
    assert (
        await client.post(BASE, headers=key, json={**body, "title": "Other"})
    ).status_code == 409
    item = created[0].json()
    assert (
        await client.post(
            BASE + "/" + item["workflow_id"] + "/draft", headers=headers(), json={"lock_version": 1}
        )
    ).status_code == 409
    results = await asyncio.gather(activate(client, item), activate(client, item))
    assert sorted(r.status_code for r in results) == [200, 409]


async def test_activity_links_cannot_cross_set_or_version_scope(api, database_engine):
    client, _ = api
    item, _ = await setup_workflow(api)
    other = await create(client, code="other-source")
    async with database_engine.connect() as connection:
        row = dict(
            (
                await connection.execute(
                    select(activity).where(activity.c.workflow_id == UUID(item["workflow_id"]))
                )
            )
            .mappings()
            .one()
        )
    for patch in [
        {"set_id": other["set_id"]},
        {"workflow_version_id": uuid4()},
        {"workflow_version_id": None},
    ]:
        with pytest.raises(DBAPIError):
            async with database_engine.begin() as connection:
                await connection.execute(
                    insert(activity).values(
                        {
                            **row,
                            "id": uuid4(),
                            "idempotency_key": uuid4(),
                            **patch,
                        }
                    )
                )
