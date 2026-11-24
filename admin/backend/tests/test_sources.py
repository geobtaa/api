import asyncio
from dataclasses import replace
from uuid import uuid4

import httpx2
import pytest
from alembic import command
from conftest import alembic_config
from sqlalchemy import func, insert, select, text
from sqlalchemy.exc import DBAPIError
from test_api import make_settings

from app.auth import Actor
from app.lifecycles.models import activity, lifecycles
from app.main import create_app
from app.sources import service
from app.sources.models import commands, sources
from app.sources.schemas import SourceCreate

pytestmark = pytest.mark.integration
BASE = "/api/v1/admin/sources"
EDITOR = Actor(
    "source-staff",
    "user",
    "Source Editor",
    None,
    frozenset({service.READ, service.CREATE, service.UPDATE}),
    frozenset(),
)


@pytest.fixture
async def api(database_engine):
    actor = [EDITOR]

    async def authenticate(_):
        return actor[0]

    app = create_app(authenticator=authenticate, settings=make_settings())
    app.state.database_engine = database_engine
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client, actor


def headers():
    return {"Idempotency-Key": str(uuid4()), "X-GEOMG-Request": "1"}


async def create(client, **fields):
    response = await client.post(
        BASE,
        headers=headers(),
        json={
            "source_id": "Synthetic_A-01",
            "title": "Example portal",
            **fields,
        },
    )
    assert response.status_code == 201, response.text
    assert response.headers["location"] == BASE + "/" + response.json()["source_id"]
    return response.json()


async def test_independent_source_create_edit_search_and_evidence(api, database_engine):
    client, _ = api
    item = await create(
        client,
        admin_notes="Staff secret",
        legacy_code="20d-0006",
        description="Public description",
        landing_page="https://example.org/browse?collection=maps#results",
    )
    assert item["source_id"] == "Synthetic_A-01" and item["lock_version"] == 1
    assert item["legacy_code"] == "20d-0006"
    assert "lifecycle_id" not in item
    path = BASE + "/" + item["source_id"]
    edited = await client.patch(
        path, headers=headers(), json={"title": "Updated portal", "lock_version": 1}
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["lock_version"] == 2
    assert edited.json()["created_at"] == item["created_at"]
    assert edited.json()["updated_at"] >= item["updated_at"]
    assert edited.json()["admin_notes"] == "Staff secret"
    assert (await client.get(path)).json() == edited.json()
    await create(client, source_id="Synthetic_B-02", title="Updated portal")
    assert (await client.get(BASE, params={"q": "20d-0006"})).json()["total"] == 1
    page = (await client.get(BASE, params={"q": "PORTAL", "limit": 1})).json()
    assert page["total"] == 2 and page["items"][0]["source_id"] == item["source_id"]
    assert (await client.get(BASE, params={"q": "portal", "offset": 1, "limit": 1})).json()[
        "items"
    ][0]["source_id"] == "Synthetic_B-02"
    assert (await client.get(BASE, params={"q": "%"})).json()["total"] == 0
    assert (await client.get(BASE, params={"q": "Synthetic_A-01"})).json()["total"] == 1
    assert (await client.get(BASE, params={"offset": 2})).json()["items"] == []
    async with database_engine.connect() as connection:
        assert await connection.scalar(select(func.count()).select_from(lifecycles)) == 0
        events = (
            (await connection.execute(select(activity).order_by(activity.c.recorded_at)))
            .mappings()
            .all()
        )
        assert [r["action"] for r in events] == [
            "source.created",
            "source.updated",
            "source.created",
        ]
        assert all(r["lifecycle_id"] is None for r in events)
        assert all(r["actor_display_name"] == EDITOR.display_name for r in events)
        assert events[1]["details"] == {
            "fields": ["title"],
            "previous_version": 1,
            "lock_version": 2,
        }
        assert "Staff secret" not in str(events)
        assert await connection.scalar(select(func.count()).select_from(commands)) == 3


async def test_concurrent_replay_generated_id_and_current_permissions(api, database_engine):
    client, actor = api
    key = headers()
    payload = {"title": "Generated identity"}
    results = await asyncio.gather(
        *[client.post(BASE, headers=key, json=payload) for _ in range(2)]
    )
    assert [r.status_code for r in results] == [201, 201]
    assert results[0].json() == results[1].json()
    item = results[0].json()
    conflict = await client.post(BASE, headers=key, json={"title": "Different"})
    assert (
        conflict.status_code == 409 and conflict.json()["detail"]["code"] == "idempotency_conflict"
    )
    path = BASE + "/" + item["source_id"]
    edit_key, patch = headers(), {"lock_version": 1, "description": "Updated"}
    results = await asyncio.gather(
        *[client.patch(path, headers=edit_key, json=patch) for _ in range(2)]
    )
    assert [r.status_code for r in results] == [200, 200]
    assert results[0].json() == results[1].json()
    actor[0] = replace(EDITOR, permissions=frozenset({service.READ}))
    assert (await client.post(BASE, headers=key, json=payload)).status_code == 403
    assert (await client.patch(path, headers=edit_key, json=patch)).status_code == 403
    async with database_engine.connect() as connection:
        assert await connection.scalar(select(func.count()).select_from(sources)) == 1
        assert await connection.scalar(select(func.count()).select_from(activity)) == 2
        assert await connection.scalar(select(func.count()).select_from(commands)) == 2


async def test_duplicate_and_concurrent_stale_version(api, database_engine):
    client, _ = api
    item = await create(client)
    duplicate = await client.post(
        BASE, headers=headers(), json={"source_id": item["source_id"], "title": "Duplicate"}
    )
    assert (
        duplicate.status_code == 409 and duplicate.json()["detail"]["code"] == "duplicate_source_id"
    )
    path = BASE + "/" + item["source_id"]
    results = await asyncio.gather(
        *[
            client.patch(path, headers=headers(), json={"title": value, "lock_version": 1})
            for value in ["One", "Two"]
        ]
    )
    assert sorted(r.status_code for r in results) == [200, 409]
    assert (
        next(r for r in results if r.status_code == 409).json()["detail"]["code"] == "stale_version"
    )
    async with database_engine.connect() as connection:
        assert await connection.scalar(select(func.count()).select_from(activity)) == 2
        assert await connection.scalar(select(func.count()).select_from(commands)) == 2


async def test_permissions_independent_of_lifecycle_and_no_public_routes(api, database_engine):
    client, actor = api
    item = await create(client)
    path = BASE + "/" + item["source_id"]
    for user, status in [
        (None, 401),
        (
            replace(
                EDITOR,
                permissions=frozenset(
                    {"lifecycles:read", "lifecycles:create", "lifecycles:update"}
                ),
            ),
            403,
        ),
        (replace(EDITOR, kind="service_account"), 403),
        (replace(EDITOR, kind="system"), 403),
    ]:
        actor[0] = user
        assert (await client.get(BASE)).status_code == status
        assert (await client.get(path)).status_code == status
        assert (
            await client.post(BASE, headers=headers(), json={"title": "Denied"})
        ).status_code == status
        assert (
            await client.patch(path, headers=headers(), json={"lock_version": 1, "title": "Denied"})
        ).status_code == status
    actor[0] = replace(
        EDITOR, permissions=frozenset({service.READ}), lifecycle_ids=frozenset({str(uuid4())})
    )
    assert (await client.get(path)).status_code == 200
    assert (await client.get(BASE)).json()["total"] == 1
    assert (await client.post(BASE, headers=headers(), json={"title": "Denied"})).status_code == 403
    assert (
        await client.patch(path, headers=headers(), json={"lock_version": 1, "title": "Denied"})
    ).status_code == 403
    assert (await client.get("/api/v1/sources")).status_code == 404
    assert (await client.get("/api/v1/sources/" + item["source_id"])).status_code == 404
    assert (await client.get(BASE + "/missing")).status_code == 404
    actor[0] = EDITOR
    assert (
        await client.patch(
            BASE + "/missing", headers=headers(), json={"lock_version": 1, "title": "Missing"}
        )
    ).status_code == 404
    with pytest.raises(service.SourceError, match="Human staff"):
        await service.mutate(
            database_engine,
            replace(EDITOR, permissions=frozenset()),
            SourceCreate(title="Denied"),
            uuid4(),
            "test",
        )


@pytest.mark.parametrize(
    "fields",
    [
        {"title": " "},
        {"title": None},
        {"title": "x" * 251},
        {"source_id": ""},
        {"source_id": "has space"},
        {"source_id": "a/b"},
        {"source_id": "x" * 129},
        {"lifecycle_id": str(uuid4())},
        {"status": "active"},
        {"description": None},
        {"admin_notes": "x" * 10001},
        {"description": "x" * 5001},
        {"landing_page": "javascript:alert(1)"},
        {"landing_page": "file:///tmp/data"},
        {"landing_page": "https://user:secret@example.org"},
        {"landing_page": "https://example.org:bad"},
        {"landing_page": "https://bad host/path"},
        {"landing_page": "https://example.org\\@evil.org"},
    ],
)
async def test_invalid_create_is_not_persisted(api, database_engine, fields):
    client, _ = api
    response = await client.post(BASE, headers=headers(), json={"title": "Example", **fields})
    assert response.status_code == 422, response.text
    async with database_engine.connect() as connection:
        for table in (sources, commands, activity):
            assert await connection.scalar(select(func.count()).select_from(table)) == 0


async def test_patch_clears_and_request_validation(api):
    client, _ = api
    item = await create(
        client, description="Description", admin_notes="Note", landing_page="https://example.org"
    )
    path = BASE + "/" + item["source_id"]
    for patch in [
        {"lock_version": 1},
        {"lock_version": 1, "title": None},
        {"lock_version": "1", "title": "X"},
        {"lock_version": 1, "source_id": "new"},
        {"lock_version": 1, "admin_notes": None},
    ]:
        assert (await client.patch(path, headers=headers(), json=patch)).status_code == 422
    result = await client.patch(
        path,
        headers=headers(),
        json={"lock_version": 1, "landing_page": None, "description": "", "admin_notes": ""},
    )
    assert result.status_code == 200
    assert result.json()["title"] == item["title"]
    assert result.json()["landing_page"] is None
    assert result.json()["description"] == result.json()["admin_notes"] == ""
    for params in [{"limit": 501}, {"limit": 0}, {"offset": -1}, {"q": "x" * 201}]:
        assert (await client.get(BASE, params=params)).status_code == 422
    assert (await client.post(BASE, json={"title": "Unsafe"})).status_code == 422
    assert (
        await client.post(BASE, headers={"X-GEOMG-Request": "1"}, json={"title": "No key"})
    ).status_code == 422


async def test_activity_failure_rolls_back_source_and_receipt(api, database_engine):
    client, _ = api
    item = await create(client)
    async with database_engine.begin() as connection:
        await connection.execute(
            text("""CREATE FUNCTION reject_source_activity() RETURNS trigger
            LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'forced private failure'; END $$""")
        )
        await connection.execute(
            text("""CREATE TRIGGER reject_source_activity BEFORE INSERT
            ON lifecycle_activity_entries FOR EACH ROW EXECUTE FUNCTION reject_source_activity()""")
        )
    key = headers()
    path = BASE + "/" + item["source_id"]
    failed = await client.patch(path, headers=key, json={"lock_version": 1, "title": "Rollback"})
    assert failed.status_code == 503 and "private failure" not in failed.text
    assert (
        await client.post(BASE, headers=headers(), json={"title": "Rollback create"})
    ).status_code == 503
    assert (await client.get(path)).json() == item
    async with database_engine.begin() as connection:
        for table in (sources, commands, activity):
            assert await connection.scalar(select(func.count()).select_from(table)) == 1
        await connection.execute(
            text("DROP TRIGGER reject_source_activity ON lifecycle_activity_entries")
        )
    assert (
        await client.patch(path, headers=key, json={"lock_version": 1, "title": "Rollback"})
    ).status_code == 200


async def test_database_subject_integrity_and_history_protection(api, database_engine):
    client, _ = api
    await create(client)
    async with database_engine.connect() as connection:
        event = dict((await connection.execute(select(activity))).mappings().one())
    for fields in [
        {"source_id": "missing"},
        {"source_id": None},
        {"lifecycle_id": uuid4()},
        {"action": "lifecycle.created"},
        {"workflow_id": uuid4(), "workflow_version_id": uuid4()},
        {"job_id": uuid4()},
        {"resource_id": "missing"},
    ]:
        with pytest.raises(DBAPIError):
            async with database_engine.begin() as connection:
                await connection.execute(
                    insert(activity).values(
                        **{**event, "id": uuid4(), "idempotency_key": uuid4(), **fields}
                    )
                )
    for sql in [
        "UPDATE sources SET source_id = 'renamed'",
        "UPDATE sources SET title = ' '",
        "UPDATE sources SET lock_version = 0",
        "DELETE FROM sources",
        "UPDATE lifecycle_activity_entries SET details = '{}'",
        "DELETE FROM lifecycle_activity_entries",
    ]:
        with pytest.raises(DBAPIError):
            async with database_engine.begin() as connection:
                await connection.execute(text(sql))
    with pytest.raises(DBAPIError, match="Cannot discard Source"):
        async with database_engine.begin() as connection:
            await connection.run_sync(lambda sync: command.downgrade(alembic_config(sync), "0012"))


async def test_migration_round_trip_preserves_legacy_activity(database_engine):
    from legacy_data import lifecycle

    async with database_engine.begin() as connection:
        await connection.run_sync(lambda sync: command.downgrade(alembic_config(sync), "0012"))
        await lifecycle(connection)
        before = (
            (await connection.execute(text("SELECT * FROM lifecycle_activity_entries")))
            .mappings()
            .one()
        )
        await connection.run_sync(lambda sync: command.upgrade(alembic_config(sync), "head"))
        after = (await connection.execute(select(activity))).mappings().one()
        assert {k: after[k] for k in before} == dict(before)
        assert after["source_id"] is None
        await connection.run_sync(lambda sync: command.downgrade(alembic_config(sync), "0012"))
        assert await connection.scalar(text("SELECT to_regclass('sources')")) is None
        await connection.run_sync(lambda sync: command.upgrade(alembic_config(sync), "head"))


async def test_durable_source_grants_and_revocation_without_lifecycle(database_engine):
    from datetime import datetime, timedelta, timezone

    from app.identity import service as identity
    from app.identity.models import grants
    from app.identity.schemas import Invitation
    from app.persistence import actors

    admin = replace(
        EDITOR, lifecycle_ids=None, permissions=EDITOR.permissions | {"identity:manage"}
    )
    verified = identity.VerifiedIdentity(
        next(iter(identity.ALLOWED_IDPS)),
        "source-staff@example.edu",
        "Source staff",
        "urn:test:mfa",
    )
    invitation = await identity.create_invitation(
        database_engine,
        admin,
        Invitation(
            idp_entity_id=verified.idp_entity_id,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            permissions=sorted(EDITOR.permissions),
            set_ids=[],
        ),
        uuid4(),
    )
    token, _ = await identity.establish_session(
        database_engine, verified, invitation["token"], 3600, ("urn:test:mfa",)
    )
    actor = await identity.authenticate_session(database_engine, token, ("urn:test:mfa",))
    assert actor.lifecycle_ids == frozenset()
    key, payload = uuid4(), SourceCreate(title="Independent authenticated Source")
    result = await service.mutate(database_engine, actor, payload, key, "test")
    async with database_engine.begin() as connection:
        actor_id = await connection.scalar(
            select(actors.c.id).where(actors.c.subject_key == actor.actor_id)
        )
        await connection.execute(
            grants.delete().where(
                grants.c.actor_id == actor_id, grants.c.permission == service.CREATE
            )
        )
    current = await identity.authenticate_session(database_engine, token, ("urn:test:mfa",))
    with pytest.raises(service.SourceError):
        await service.mutate(database_engine, current, payload, key, "test")
    async with database_engine.connect() as connection:
        assert (
            await service.get_source(connection, current, result.source_id)
        ).source_id == result.source_id
        assert await connection.scalar(select(func.count()).select_from(lifecycles)) == 0
