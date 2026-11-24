from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from test_identity import CONTEXTS, IDENTITY
from test_sets import api as api
from test_sets import create, headers
from test_work import BASE, PERMISSIONS, setup, task

from app.identity import service
from app.identity.models import sessions
from app.identity.schemas import AccountChange, Invitation

pytestmark = pytest.mark.integration


async def test_current_set_grants_bound_sessions_work_assignment_and_retry(api, database_engine):
    client, current, subject = await setup(api)
    other = await create(client, set_id="other")
    first = await task(client, subject)
    await task(client, other)
    administrator = replace(
        current[0], permissions=current[0].permissions | {"identity:manage"}, lifecycle_ids=None
    )
    permissions = sorted(PERMISSIONS | {"sets:read", "sources:read", "admin.session:read"})
    administrator = replace(administrator, permissions=administrator.permissions | set(permissions))
    invitation = Invitation(
        idp_entity_id=IDENTITY.idp_entity_id,
        expires_at=datetime.now(UTC) + timedelta(days=1),
        permissions=permissions,
        set_ids=[subject["set_id"]],
    )
    key = uuid4()
    issued = await service.create_invitation(database_engine, administrator, invitation, key)
    with pytest.raises(service.DomainError, match="Invitation key already used"):
        await service.create_invitation(
            database_engine,
            administrator,
            invitation.model_copy(update={"set_ids": [other["set_id"]]}),
            key,
        )
    token, _ = await service.establish_session(
        database_engine, IDENTITY, issued["token"], 3600, CONTEXTS
    )
    staff = await service.authenticate_session(database_engine, token, CONTEXTS)
    assert staff.set_ids == {subject["set_id"]}
    current[0] = staff
    assert (await client.get(BASE)).json()["total"] == 1
    assert (await client.get("/api/v1/admin/sets")).json()["total"] == 1
    assert (await client.get("/api/v1/admin/session")).json()["actor"]["set_ids"] == [
        subject["set_id"]
    ]
    async with database_engine.connect() as connection:
        target_id = await connection.scalar(
            select(sessions.c.actor_id).where(sessions.c.token_hash == service.token_hash(token))
        )
    # A globally authorized staff member cannot assign someone outside their Set grant.
    current[0] = administrator
    allowed = (await client.get(BASE + "/assignees", params={"set_id": subject["set_id"]})).json()
    denied = (await client.get(BASE + "/assignees", params={"set_id": other["set_id"]})).json()
    assert any(person["actor_id"] == str(target_id) for person in allowed)
    assert all(person["actor_id"] != str(target_id) for person in denied)
    current[0] = staff
    path = BASE + "/" + first["task_id"]
    request_key = headers()
    body = {"lock_version": 1, "title": "Scoped edit", "reason": "Test current access"}
    assert (await client.patch(path, headers=request_key, json=body)).status_code == 200
    change = AccountChange(active=True, permissions=permissions, set_ids=[], lock_version=1)
    await service.change_account(database_engine, administrator, target_id, change, uuid4())
    current[0] = await service.authenticate_session(database_engine, token, CONTEXTS)
    assert current[0].set_ids == frozenset()
    assert (await client.get(BASE)).json()["total"] == 0
    assert (await client.patch(path, headers=request_key, json=body)).status_code == 404
    detail = await service.account_detail(database_engine, administrator, target_id)
    assert detail["set_ids"] == [] and detail["lock_version"] == 2
    with pytest.raises(service.DomainError, match="Set not found"):
        await service.change_account(
            database_engine,
            administrator,
            target_id,
            change.model_copy(update={"lock_version": 2, "set_ids": ["missing"]}),
            uuid4(),
        )
    assert (await service.account_detail(database_engine, administrator, target_id))[
        "lock_version"
    ] == 2


async def test_set_grant_migration_preserves_catalog_scope_and_refuses_unsafe_downgrade(
    api, database_engine
):
    from alembic import command
    from conftest import alembic_config
    from sqlalchemy import insert, text, update

    from app.identity.models import accounts, set_scopes
    from app.persistence import actors

    client, _, subject = await setup(api)
    async with database_engine.begin() as connection:
        await connection.run_sync(lambda sync: command.downgrade(alembic_config(sync), "0019"))
        actor_id = await connection.scalar(
            select(actors.c.id).where(actors.c.subject_key == "set-staff")
        )
        await connection.execute(
            text(
                "INSERT INTO identity_accounts (actor_id, all_lifecycles) VALUES (:actor_id, false)"
            ),
            {"actor_id": actor_id},
        )
        await connection.run_sync(lambda sync: command.upgrade(alembic_config(sync), "0020"))
        saved = (
            (await connection.execute(select(actors).where(actors.c.id == actor_id)))
            .mappings()
            .one()
        )
        resolved = await service.resolve_actor(connection, saved)
        assert resolved.set_ids is None
        assert resolved.lifecycle_ids == frozenset()
        await connection.execute(
            update(accounts).where(accounts.c.actor_id == actor_id).values(all_sets=False)
        )
        await connection.execute(
            insert(set_scopes).values(actor_id=actor_id, set_id=subject["set_id"])
        )
        resolved = await service.resolve_actor(connection, saved)
        assert resolved.set_ids == {subject["set_id"]}
    with pytest.raises(Exception, match="Cannot discard scoped Set grants"):
        async with database_engine.begin() as connection:
            await connection.run_sync(lambda sync: command.downgrade(alembic_config(sync), "0019"))
