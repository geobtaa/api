import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from alembic import command
from conftest import alembic_config
from sqlalchemy import func, insert, select, text
from sqlalchemy.exc import DBAPIError
from test_sources import BASE, EDITOR, create, headers
from test_sources import api as source_api

from app.lifecycles.models import activity, lifecycles
from app.sources import activity as service
from app.sources.models import commands, sources
from app.sources.schemas import SourceActivityCreate
from app.sources.service import SourceError

api = source_api
pytestmark = pytest.mark.integration
STAFF = replace(EDITOR, permissions=EDITOR.permissions | {service.READ, service.CREATE})
BODY = {"action": "review.completed", "outcome": "succeeded", "reason": "Reviewed source metadata"}


async def setup(api):
    client, actor = api
    actor[0] = STAFF
    item = await create(client, admin_notes="Source secret")
    return client, actor, item, BASE + "/" + item["source_id"] + "/activity"


async def test_record_and_paginate_source_history_without_lifecycle(api, database_engine):
    client, actors, source, path = await setup(api)
    initial = (await client.get(path)).json()
    assert initial["total"] == 1
    assert initial["items"][0]["action"] == "source.created"
    assert "Source secret" not in str(initial)
    events = []
    for outcome in ["succeeded", "partially_succeeded", "failed", "cancelled", "rejected"]:
        response = await client.post(
            path,
            headers=headers(),
            json={
                **BODY,
                "outcome": outcome,
                "occurred_at": "2024-01-15T06:30:00-06:00",
            },
        )
        assert response.status_code == 201, response.text
        event = response.json()
        assert event["source_id"] == source["source_id"]
        assert event["actor_display_name"] == STAFF.display_name
        assert event["occurred_at"] == "2024-01-15T12:30:00Z"
        assert event["outcome"] == outcome
        assert event["origin"] == "geomg-staff"
        assert event["details"] == {"source_version": 1, "recording": "staff_reported"}
        events.append(event)
    await create(client, source_id="other", title="Other")
    assert (await client.get(BASE + "/other/activity")).json()["total"] == 1
    expected = [initial["items"][0]["id"]] + sorted([e["id"] for e in events], reverse=True)
    actual = []
    for offset in [0, 2, 4]:
        page = (await client.get(path, params={"limit": 2, "offset": offset})).json()
        assert page["total"] == 6
        actual.extend(item["id"] for item in page["items"])
    assert actual == expected
    assert (await client.get(path, params={"offset": 6})).json()["items"] == []
    actors[0] = replace(STAFF, display_name="Renamed staff")
    assert (await client.get(path)).json()["items"][0]["actor_display_name"] == STAFF.display_name
    assert (await client.get(BASE + "/" + source["source_id"])).json() == source
    async with database_engine.connect() as connection:
        assert await connection.scalar(select(func.count()).select_from(lifecycles)) == 0
        assert await connection.scalar(select(func.count()).select_from(commands)) == 7
        assert (
            await connection.scalar(
                select(func.count())
                .select_from(activity)
                .where(activity.c.lifecycle_id.is_not(None))
            )
            == 0
        )


async def test_replay_conflicts_and_current_access(api, database_engine):
    client, actors, _, path = await setup(api)
    key = headers()
    results = await asyncio.gather(*[client.post(path, headers=key, json=BODY) for _ in range(2)])
    assert [r.status_code for r in results] == [201, 201]
    assert results[0].json() == results[1].json()
    event = results[0].json()
    assert datetime.fromisoformat(event["occurred_at"]) <= datetime.now(UTC)
    assert datetime.fromisoformat(event["recorded_at"]) >= datetime.fromisoformat(
        event["occurred_at"]
    )
    for field in [{"action": "harvest.completed"}, {"outcome": "failed"}, {"reason": "Different"}]:
        conflict = await client.post(path, headers=key, json={**BODY, **field})
        assert conflict.status_code == 409
        assert conflict.json()["detail"]["code"] == "idempotency_conflict"
    actors[0] = replace(STAFF, permissions=STAFF.permissions - {service.CREATE})
    assert (await client.post(path, headers=key, json=BODY)).status_code == 403
    actors[0] = replace(STAFF, permissions=STAFF.permissions - {"sources:read"})
    assert (await client.post(path, headers=key, json=BODY)).status_code == 403
    actors[0] = STAFF
    assert (await client.post(path, headers=key, json=BODY)).json() == event
    # A request key is scoped to its actor and Source, not globally consumed.
    await create(client, source_id="other")
    assert (await client.post(BASE + "/other/activity", headers=key, json=BODY)).status_code == 201
    actors[0] = replace(STAFF, actor_id="another-staff")
    assert (await client.post(path, headers=key, json=BODY)).status_code == 201
    async with database_engine.connect() as connection:
        assert await connection.scalar(select(func.count()).select_from(activity)) == 5
        assert await connection.scalar(select(func.count()).select_from(commands)) == 5


async def test_history_and_write_permissions_are_separate(api, database_engine):
    client, actors, source, path = await setup(api)
    for actor, expected in [
        (None, 401),
        (EDITOR, 403),
        (replace(STAFF, permissions=frozenset({service.READ, service.CREATE})), 403),
        (replace(STAFF, permissions=EDITOR.permissions | {"lifecycle-activity:read"}), 403),
        (replace(STAFF, kind="service_account"), 403),
        (replace(STAFF, kind="system"), 403),
    ]:
        actors[0] = actor
        assert (await client.get(path)).status_code == expected
        assert (await client.post(path, headers=headers(), json=BODY)).status_code == expected
    actors[0] = replace(STAFF, permissions=frozenset({"sources:read", service.READ}))
    assert (await client.get(path)).status_code == 200
    assert (await client.post(path, headers=headers(), json=BODY)).status_code == 403
    actors[0] = replace(STAFF, permissions=frozenset({"sources:read", service.CREATE}))
    assert (await client.post(path, headers=headers(), json=BODY)).status_code == 201
    assert (await client.get(path)).status_code == 403
    actors[0] = STAFF
    assert (await client.get(BASE + "/missing/activity")).status_code == 404
    assert (
        await client.post(BASE + "/missing/activity", headers=headers(), json=BODY)
    ).status_code == 404
    for params in [{"offset": -1}, {"limit": 0}, {"limit": 501}]:
        assert (await client.get(path, params=params)).status_code == 422
    assert (await client.post(path, json=BODY)).status_code == 422
    assert (await client.post(path, headers={"X-GEOMG-Request": "1"}, json=BODY)).status_code == 422
    assert (
        await client.get("/api/v1/sources/" + source["source_id"] + "/activity")
    ).status_code == 404
    with pytest.raises(SourceError) as error:
        await service.record(
            database_engine,
            EDITOR,
            source["source_id"],
            SourceActivityCreate(**BODY),
            uuid4(),
            "test",
        )
    assert error.value.status == 403


@pytest.mark.parametrize(
    "fields",
    [
        {"action": "source.updated"},
        {"action": "workflow.activated"},
        {"outcome": "running"},
        {"reason": " "},
        {"reason": "x" * 1001},
        {"reason": None},
        {"occurred_at": "2024-01-01T00:00:00"},
        {"occurred_at": "bad"},
        {"occurred_at": (datetime.now(UTC) + timedelta(days=365)).isoformat()},
        {"source_id": "different"},
        {"lifecycle_id": str(uuid4())},
        {"actor_id": str(uuid4())},
        {"origin": "automated"},
        {"details": {"count": 100}},
        {"recorded_at": "2024-01-01T00:00:00Z"},
    ],
)
async def test_invalid_activity_never_writes(api, database_engine, fields):
    client, _, _, path = await setup(api)
    response = await client.post(path, headers=headers(), json={**BODY, **fields})
    assert response.status_code == 422, response.text
    async with database_engine.connect() as connection:
        assert await connection.scalar(select(func.count()).select_from(activity)) == 1
        assert await connection.scalar(select(func.count()).select_from(commands)) == 1


@pytest.mark.parametrize(
    "table,operation", [("lifecycle_activity_entries", "INSERT"), ("source_commands", "UPDATE")]
)
async def test_atomic_failure_and_retry(api, database_engine, table, operation):
    client, _, source, path = await setup(api)
    async with database_engine.begin() as connection:
        await connection.execute(
            text("""CREATE FUNCTION reject_source_work() RETURNS trigger
            LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'private test failure'; END $$""")
        )
        await connection.execute(
            text(
                f"CREATE TRIGGER reject_work BEFORE {operation} ON {table} "
                "FOR EACH ROW EXECUTE FUNCTION reject_source_work()"
            )
        )
    key = headers()
    response = await client.post(path, headers=key, json=BODY)
    assert response.status_code == 503 and "private test failure" not in response.text
    async with database_engine.begin() as connection:
        assert await connection.scalar(select(func.count()).select_from(activity)) == 1
        assert await connection.scalar(select(func.count()).select_from(commands)) == 1
        assert await connection.scalar(select(sources.c.lock_version)) == source["lock_version"]
        await connection.execute(text(f"DROP TRIGGER reject_work ON {table}"))
    assert (await client.post(path, headers=key, json=BODY)).status_code == 201


async def test_source_work_does_not_complete_set_tasks_or_change_maintenance(api):
    from test_sets import BASE as SET
    from test_work import PERMISSIONS, task

    from app.sets import service as set_service

    client, actors, source, path = await setup(api)
    actors[0] = replace(
        STAFF,
        permissions=STAFF.permissions
        | PERMISSIONS
        | {set_service.READ, set_service.CREATE, set_service.HISTORY, "sources:use"},
    )
    created = await client.post(
        SET,
        headers=headers(),
        json={"set_id": "source-work", "source_id": source["source_id"], "title": "Managed Set"},
    )
    assert created.status_code == 201, created.text
    subject = created.json()
    work = await task(client, subject)
    maintenance_path = SET + "/source-work/maintenance"
    before = (await client.get(maintenance_path)).json()
    history = (await client.get(SET + "/source-work/activity")).json()
    for action in ["review.completed", "harvest.completed"]:
        assert (
            await client.post(path, headers=headers(), json={**BODY, "action": action})
        ).status_code == 201
    assert (await client.get(maintenance_path)).json() == before
    assert (await client.get(SET + "/source-work/activity")).json() == history
    assert (await client.get("/api/v1/admin/tasks/" + work["task_id"])).json() == work
    assert (await client.get(path)).json()["total"] == 3


async def test_migration_preserves_evidence_and_rejects_invalid_subjects(api, database_engine):
    client, _, _, path = await setup(api)
    async with database_engine.begin() as connection:
        before = dict((await connection.execute(select(activity))).mappings().one())
        await connection.run_sync(lambda sync: command.downgrade(alembic_config(sync), "0013"))
        await connection.run_sync(lambda sync: command.upgrade(alembic_config(sync), "head"))
        assert dict((await connection.execute(select(activity))).mappings().one()) == before
    created = await client.post(path, headers=headers(), json=BODY)
    event_id = UUID(created.json()["id"])
    async with database_engine.connect() as connection:
        row = dict(
            (await connection.execute(select(activity).where(activity.c.id == event_id)))
            .mappings()
            .one()
        )
    for patch in [
        {"source_id": "missing"},
        {"source_id": None},
        {"lifecycle_id": uuid4()},
        {"workflow_id": uuid4(), "workflow_version_id": uuid4()},
        {"job_id": uuid4()},
        {"resource_id": "resource"},
        {"action": "workflow.activated"},
        {"outcome": "unknown"},
    ]:
        with pytest.raises(DBAPIError):
            async with database_engine.begin() as connection:
                await connection.execute(
                    insert(activity).values(
                        {**row, "id": uuid4(), "idempotency_key": uuid4(), **patch}
                    )
                )
    for sql in [
        "UPDATE lifecycle_activity_entries SET reason = 'rewrite'",
        "DELETE FROM lifecycle_activity_entries",
    ]:
        with pytest.raises(DBAPIError):
            async with database_engine.begin() as connection:
                await connection.execute(text(sql))
    with pytest.raises(DBAPIError, match="Cannot discard Source work history"):
        async with database_engine.begin() as connection:
            await connection.run_sync(lambda sync: command.downgrade(alembic_config(sync), "0013"))
