import asyncio
from dataclasses import replace

import pytest
from alembic import command
from conftest import alembic_config
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError
from test_sets import BASE, create, headers
from test_sets import api as api

from app.lifecycles.models import activity
from app.sets.models import commands

pytestmark = pytest.mark.integration


async def setup(api):
    client, actor = api
    actor[0] = replace(
        actor[0],
        permissions=actor[0].permissions
        | {
            "sets:retire",
            "sets:restore",
            "sets:retired-read",
            "tasks:read",
            "tasks:create",
            "tasks:update",
            "tasks:complete",
            "work:configure",
        },
    )
    item = await create(client)
    return client, actor, item, BASE + "/" + item["set_id"]


def change(target, version=1, **values):
    return {
        "target": target,
        "lock_version": version,
        "reason": "Work plan changed",
        "confirmed": True,
        **values,
    }


async def test_state_transitions_retired_discovery_and_edit_guards(api, database_engine):
    client, actor, item, path = await setup(api)
    for target, version in [("inactive", 1), ("active", 2), ("retired", 3)]:
        preview = await client.get(path + "/state-preview", params={"target": target})
        assert preview.status_code == 200, preview.text
        assert preview.json()["lock_version"] == version
        assert preview.json()["can_proceed"]
        result = await client.put(path + "/state", headers=headers(), json=change(target, version))
        assert result.status_code == 200, result.text
        assert result.json()["status"] == target
        assert result.json()["lock_version"] == version + 1
    assert (await client.get(BASE)).json()["total"] == 0
    assert (await client.get(BASE, params={"status": "retired"})).json()["total"] == 1
    assert (
        await client.patch(path, headers=headers(), json={"lock_version": 4, "title": "X"})
    ).status_code == 409
    assert (
        await client.post(
            "/api/v1/admin/tasks",
            headers=headers(),
            json={
                "set_id": item["set_id"],
                "title": "Blocked",
                "work_type": "other",
                "due_on": "2026-09-23",
            },
        )
    ).status_code == 409
    assert (
        await client.put(
            path + "/maintenance/review",
            headers=headers(),
            json={
                "lock_version": 0,
                "interval": "P1M",
                "enabled": False,
            },
        )
    ).status_code == 409
    assert (
        await client.put(path + "/state", headers=headers(), json=change("active", 4))
    ).status_code == 409
    assert (
        await client.put(path + "/state", headers=headers(), json=change("inactive", 4))
    ).status_code == 200
    assert (await client.get(BASE)).json()["items"][0]["status"] == "inactive"
    events = (await client.get(path + "/activity")).json()["items"]
    assert events[0]["action"] == "set.restored" and events[0]["reason"] == "Work plan changed"
    async with database_engine.connect() as connection:
        assert await connection.scalar(select(func.count()).select_from(activity)) == 5
    actor[0] = replace(actor[0], permissions=actor[0].permissions - {"sets:retired-read"})
    assert (await client.get(BASE, params={"status": "retired"})).status_code == 403
    assert "retired" not in (await client.get("/api/v1/admin/contracts/sets")).json()["states"]


async def test_no_status_bypass_and_confirmed_versioned_commands(api):
    client, _, _, path = await setup(api)
    for target in ["active", "inactive", "retired"]:
        assert (
            await client.patch(path, headers=headers(), json={"lock_version": 1, "status": target})
        ).status_code == 422
    assert (
        await client.post(
            BASE, headers=headers(), json={"source_id": "parent", "title": "X", "status": "retired"}
        )
    ).status_code == 422
    for values in [
        {"confirmed": False},
        {"confirmed": 1},
        {"reason": "  "},
        {"reason": "x" * 1001},
        {"lock_version": 0},
    ]:
        assert (
            await client.put(path + "/state", headers=headers(), json=change("inactive", **values))
        ).status_code == 422
    assert (await client.put(path + "/state", json=change("inactive"))).status_code == 422
    preview = (await client.get(path + "/state-preview?target=inactive")).json()
    assert (
        await client.patch(path, headers=headers(), json={"lock_version": 1, "title": "Updated"})
    ).status_code == 200
    failed = await client.put(
        path + "/state", headers=headers(), json=change("inactive", preview["lock_version"])
    )
    assert failed.status_code == 409 and failed.json()["detail"]["code"] == "stale_version"
    assert (await client.get(path)).json()["status"] == "active"


async def test_state_retries_reauthorize_the_original_action_and_scope(api):
    client, actor, _, path = await setup(api)
    retire = change("retired")
    assert (await client.put(path + "/state", headers=headers(), json=retire)).status_code == 200
    key = headers()
    restoration = change("inactive", 2)
    first = await client.put(path + "/state", headers=key, json=restoration)
    assert first.status_code == 200
    assert (
        await client.put(path + "/state", headers=headers(), json=change("active", 3))
    ).status_code == 200
    assert (await client.put(path + "/state", headers=key, json=restoration)).json() == first.json()
    actor[0] = replace(actor[0], permissions=actor[0].permissions - {"sets:restore"})
    assert (await client.put(path + "/state", headers=key, json=restoration)).status_code == 403
    actor[0] = replace(
        actor[0], permissions=actor[0].permissions | {"sets:restore"}, set_ids=frozenset()
    )
    assert (await client.put(path + "/state", headers=key, json=restoration)).status_code == 404
    assert (await client.get(path + "/state-preview?target=inactive")).status_code == 404


async def test_retirement_rechecks_tasks_created_after_preview(api):
    client, _, item, path = await setup(api)
    assert (await client.get(path + "/state-preview?target=retired")).json()["can_proceed"]
    task = await client.post(
        "/api/v1/admin/tasks",
        headers=headers(),
        json={
            "set_id": item["set_id"],
            "title": "A new review",
            "work_type": "review",
            "due_on": "2026-09-23",
        },
    )
    assert task.status_code == 201, task.text
    preview = (await client.get(path + "/state-preview?target=retired")).json()
    assert preview["open_tasks"] == 1 and not preview["can_proceed"]
    result = await client.put(path + "/state", headers=headers(), json=change("retired"))
    assert result.status_code == 409 and result.json()["detail"]["code"] == "open_tasks"
    assert (await client.get(path)).json()["lock_version"] == 1


async def test_concurrent_state_and_task_creation_cannot_retire_unfinished_work(api):
    client, _, item, path = await setup(api)
    retire, task = await asyncio.gather(
        client.put(path + "/state", headers=headers(), json=change("retired")),
        client.post(
            "/api/v1/admin/tasks",
            headers=headers(),
            json={
                "set_id": item["set_id"],
                "title": "Concurrent review",
                "work_type": "review",
                "due_on": "2026-09-23",
            },
        ),
    )
    assert (retire.status_code, task.status_code) in {(200, 409), (409, 201)}


async def test_concurrent_state_replay_and_changed_body(api, database_engine):
    client, _, _, path = await setup(api)
    key = headers()
    results = await asyncio.gather(
        *[client.put(path + "/state", headers=key, json=change("inactive")) for _ in range(2)]
    )
    assert [result.status_code for result in results] == [200, 200]
    assert results[0].json() == results[1].json()
    conflict = await client.put(
        path + "/state", headers=key, json=change("inactive", reason="Different")
    )
    assert (
        conflict.status_code == 409 and conflict.json()["detail"]["code"] == "idempotency_conflict"
    )
    async with database_engine.connect() as connection:
        assert await connection.scalar(select(func.count()).select_from(commands)) == 2


async def test_activation_rolls_back_generated_tasks_state_and_receipt(api, database_engine):
    client, _, _, path = await setup(api)
    assert (
        await client.put(path + "/state", headers=headers(), json=change("inactive"))
    ).status_code == 200
    # A paused rule can have a next due date without generating an open occurrence.
    assert (
        await client.put(
            path + "/maintenance/review",
            headers=headers(),
            json={
                "lock_version": 0,
                "interval": "P1M",
                "enabled": False,
                "next_due_on": "2026-09-01",
            },
        )
    ).status_code == 200
    async with database_engine.begin() as connection:
        await connection.execute(text("UPDATE set_maintenance SET enabled = true"))
        await connection.execute(
            text("""CREATE FUNCTION reject_state_evidence() RETURNS trigger
        LANGUAGE plpgsql AS $$ BEGIN IF NEW.action = 'set.activated' THEN
        RAISE EXCEPTION 'forced private failure'; END IF; RETURN NEW; END $$""")
        )
        await connection.execute(
            text("""CREATE TRIGGER reject_state_evidence BEFORE INSERT
        ON lifecycle_activity_entries FOR EACH ROW EXECUTE FUNCTION reject_state_evidence()""")
        )
        count = await connection.scalar(select(func.count()).select_from(commands))
    key = headers()
    failed = await client.put(path + "/state", headers=key, json=change("active", 2))
    assert failed.status_code == 503 and "private failure" not in failed.text
    assert (await client.get(path)).json()["status"] == "inactive"
    assert (await client.get("/api/v1/admin/tasks")).json()["total"] == 0
    async with database_engine.begin() as connection:
        assert await connection.scalar(select(func.count()).select_from(commands)) == count
        await connection.execute(
            text("DROP TRIGGER reject_state_evidence ON lifecycle_activity_entries")
        )
    assert (
        await client.put(path + "/state", headers=key, json=change("active", 2))
    ).status_code == 200
    assert (await client.get("/api/v1/admin/tasks")).json()["total"] == 1
    with pytest.raises(DBAPIError, match="Cannot discard Set state history"):
        async with database_engine.begin() as connection:
            await connection.run_sync(lambda sync: command.downgrade(alembic_config(sync), "0020"))


async def test_separate_retirement_permission_and_state_contract(api):
    client, actor, _, path = await setup(api)
    actor[0] = replace(actor[0], permissions=actor[0].permissions - {"sets:retire", "sets:restore"})
    contract = (await client.get("/api/v1/admin/contracts/sets")).json()
    assert {action["target"] for action in contract["state_actions"]} == {"inactive", "active"}
    assert (await client.get(path + "/state-preview?target=retired")).status_code == 403
    assert (
        await client.put(path + "/state", headers=headers(), json=change("retired"))
    ).status_code == 403
    actor[0] = replace(actor[0], kind="service_account")
    assert (
        await client.put(path + "/state", headers=headers(), json=change("inactive"))
    ).status_code == 403
