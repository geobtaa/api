import asyncio
import hashlib
from dataclasses import replace
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, insert, select, text, update
from sqlalchemy.exc import DBAPIError
from test_managing_sets import EDITOR, create, headers
from test_managing_sets import api as set_api
from test_workflows import activate, process

from app.activity import activity
from app.jobs import service, worker
from app.jobs.models import artifacts, attempts, items, jobs
from app.resources.models import resources

api = set_api
pytestmark = pytest.mark.integration
BASE = "/api/v1/admin/jobs"
MANAGER = replace(
    EDITOR,
    permissions=EDITOR.permissions
    | {
        "jobs:read",
        "jobs:submit",
        "jobs:cancel",
        "jobs:artifacts:read",
        "resources:read",
        "workflows:read",
        "workflows:change",
        "workflows:activate",
        "sets:retire",
    },
)


async def setup(api, engine, count=2):
    client, actor = api
    actor[0] = MANAGER
    scope = await create(client)
    lid = scope["set_id"]
    async with engine.begin() as connection:
        aid = await connection.scalar(select(activity.c.actor_id).where(activity.c.set_id == lid))
        await connection.execute(
            insert(resources),
            [
                dict(
                    id=f"resource-{n}",
                    set_id=lid,
                    dct_title_s=f"Resource {n}",
                    created_by_actor_id=aid,
                    publication_state="draft",
                )
                for n in range(count)
            ],
        )
    body = {
        "set_id": str(lid),
        "selection": [{"resource_id": f"resource-{n}", "lock_version": 1} for n in range(count)],
    }
    return body, scope


async def submit(client, body, key=None):
    result = await client.post(BASE, headers=headers(key), json=body)
    assert result.status_code == 202, result.text
    return result.json()


def resolver(actor):
    async def resolve(connection, subject):
        return actor[0]

    return resolve


async def test_replay_bounded_results_report_and_reconciliation(api, database_engine):
    client, actor = api
    body, _ = await setup(api, database_engine, 12)
    key = uuid4()
    first, second = await asyncio.gather(submit(client, body, key), submit(client, body, key))
    assert first["job_id"] == second["job_id"]
    jid = UUID(first["job_id"])
    assert first["totals"] == {"pending": 12}
    listing = (await client.get(BASE + "?limit=1")).json()
    assert listing["total"] == 1 and listing["items"][0]["job_id"] == str(jid)
    assert (await client.get("/api/v1/admin/contracts/jobs")).json() == {
        "can_cancel": True,
        "can_download": True,
    }
    changed = {**body, "selection": body["selection"][:1]}
    assert (await client.post(BASE, headers=headers(key), json=changed)).status_code == 409
    assert (await client.get(f"{BASE}/{jid}/report")).status_code == 404
    lease = await worker.claim(database_engine)
    assert lease[0] == jid
    assert await worker.claim(database_engine) is None
    assert await worker.step(database_engine, *lease, resolver(actor)) is True
    progress = (await client.get(f"{BASE}/{jid}")).json()
    assert progress["totals"] == {"pending": 2, "unchanged": 10}
    assert await worker.step(database_engine, *lease, resolver(actor)) is False
    assert await worker.step(database_engine, *lease, resolver(actor)) is False
    report = await client.get(f"{BASE}/{jid}/report")
    assert report.status_code == 200
    assert report.headers["etag"] == '"' + hashlib.sha256(report.content).hexdigest() + '"'
    assert report.json()["totals"] == {"unchanged": 12}
    page = (await client.get(f"{BASE}/{jid}/items?offset=10&limit=1")).json()
    assert page["total"] == 12 and page["items"][0]["position"] == 11
    assert (await client.get(f"{BASE}/{jid}/items?limit=501")).status_code == 422
    async with database_engine.connect() as connection:
        fact = (
            (await connection.execute(select(activity).where(activity.c.job_id == jid)))
            .mappings()
            .one()
        )
        assert fact["outcome"] == "succeeded" and fact["details"]["total"] == 12
        assert fact["details"]["totals"] == report.json()["totals"]
    assert (await submit(client, body, key))["state"] == "succeeded"
    actor[0] = replace(MANAGER, permissions=MANAGER.permissions - {"jobs:artifacts:read"})
    assert (await client.get(f"{BASE}/{jid}/report")).status_code == 403
    actor[0] = replace(MANAGER, set_ids=frozenset())
    assert (await client.get(f"{BASE}/{jid}")).status_code == 404
    assert (await client.get(BASE)).json()["total"] == 0
    actor[0] = MANAGER
    async with database_engine.begin() as connection:
        await connection.execute(update(artifacts).values(expires_at=func.clock_timestamp()))
        await service.expire_artifacts(connection)
        artifact = (await connection.execute(select(artifacts))).mappings().one()
        assert artifact["content"] is None and artifact["expired_at"] and artifact["checksum"]
    assert (await client.get(f"{BASE}/{jid}/report")).status_code == 410


async def test_recovery_fences_old_worker_and_preserves_committed_items(api, database_engine):
    client, actor = api
    body, _ = await setup(api, database_engine, 12)
    await submit(client, body)
    lease = await worker.claim(database_engine)
    assert await worker.step(database_engine, *lease, resolver(actor))
    async with database_engine.begin() as connection:
        await connection.execute(update(jobs).values(lease_until=func.clock_timestamp()))
    replacement = await worker.claim(database_engine)
    assert replacement[1] != lease[1]
    assert await worker.step(database_engine, *lease, resolver(actor)) is False
    assert await worker.step(database_engine, *replacement, resolver(actor)) is False
    async with database_engine.connect() as connection:
        assert (
            await connection.execute(select(attempts.c.state).order_by(attempts.c.number))
        ).scalars().all() == ["expired", "succeeded"]
        assert (
            await connection.scalar(
                select(func.count()).select_from(activity).where(activity.c.job_id == lease[0])
            )
            == 1
        )


async def test_revocation_conflicts_cancellation_and_retirement(api, database_engine):
    client, actor = api
    body, scope = await setup(api, database_engine)
    job = await submit(client, body)
    jid = job["job_id"]
    lid = scope["set_id"]
    preview = await client.get(f"/api/v1/admin/sets/{lid}/state-preview?target=retired")
    # The command guard is authoritative regardless of when a preview was loaded.
    result = await client.put(
        f"/api/v1/admin/sets/{lid}/state",
        headers=headers(),
        json={
            "target": "retired",
            "lock_version": 1,
            "confirmed": True,
            "reason": "Source closed",
        },
    )
    assert result.status_code == 409, result.text
    lease = await worker.claim(database_engine)
    actor[0] = replace(MANAGER, permissions=MANAGER.permissions - {"jobs:submit"})
    assert await worker.step(database_engine, *lease, resolver(actor)) is False
    assert (await client.get(f"{BASE}/{jid}")).json()["state"] == "rejected"
    actor[0] = MANAGER
    job = await submit(client, body)
    lease = await worker.claim(database_engine)
    async with database_engine.begin() as connection:
        await connection.execute(
            update(resources).where(resources.c.id == "resource-0").values(lock_version=2)
        )
        await connection.execute(
            update(resources).where(resources.c.id == "resource-1").values(dct_title_s="")
        )
    assert not await worker.step(database_engine, *lease, resolver(actor))
    assert (await client.get(f"{BASE}/{job['job_id']}")).json()["totals"] == {
        "conflicted": 1,
        "invalid": 1,
    }
    body["selection"][0]["lock_version"] = 2
    job = await submit(client, body)
    path = f"{BASE}/{job['job_id']}/cancel"
    assert (await client.post(path, headers=headers())).json()["state"] == "cancelled"
    assert (await client.post(path, headers=headers())).json()["state"] == "cancelled"
    assert (
        await client.put(
            f"/api/v1/admin/sets/{lid}/state",
            headers=headers(),
            json={
                "target": "retired",
                "lock_version": 1,
                "confirmed": True,
                "reason": "Source closed",
            },
        )
    ).status_code == 200
    assert (await client.post(BASE, headers=headers(), json=body)).status_code == 409
    assert preview.status_code == 200
    assert preview.json()["active_jobs"] == 1
    assert preview.json()["can_proceed"] is False


async def test_submission_validation_and_workflow_pinning(api, database_engine):
    client, actor = api
    body, scope = await setup(api, database_engine)
    for changed, expected in [
        ({**body, "selection": []}, 422),
        ({**body, "selection": body["selection"] * 2}, 422),
        ({**body, "selection": [{"resource_id": "missing", "lock_version": 1}]}, 404),
        ({**body, "selection": [{"resource_id": "resource-0", "lock_version": 2}]}, 409),
        ({**body, "set_id": str(uuid4())}, 404),
        ({**body, "workflow_version_id": str(uuid4())}, 404),
    ]:
        assert (await client.post(BASE, headers=headers(), json=changed)).status_code == expected
    w = (
        await client.post(
            "/api/v1/admin/workflows",
            headers=headers(),
            json={
                "set_id": scope["set_id"],
                "title": "Validate",
                "processes": [process(kind="validate")],
            },
        )
    ).json()
    body["workflow_version_id"] = w["draft"]["version_id"]
    assert (await client.post(BASE, headers=headers(), json=body)).status_code == 422
    w = (await activate(client, w)).json()
    job = await submit(client, body)
    draft = (
        await client.post(
            f"/api/v1/admin/workflows/{w['workflow_id']}/draft",
            headers=headers(),
            json={"lock_version": w["lock_version"]},
        )
    ).json()
    await activate(client, draft)
    lease = await worker.claim(database_engine)
    assert not await worker.step(database_engine, *lease, resolver(actor))
    async with database_engine.connect() as connection:
        fact = (
            (
                await connection.execute(
                    select(activity).where(activity.c.job_id == UUID(job["job_id"]))
                )
            )
            .mappings()
            .one()
        )
        assert str(fact["workflow_version_id"]) == body["workflow_version_id"]
    actor[0] = replace(MANAGER, kind="service_account")
    assert (await client.post(BASE, headers=headers(), json=body)).status_code == 403


async def test_failed_transaction_recovery_exhaustion_and_missing_reads(api, database_engine):
    client, actor = api
    body, _ = await setup(api, database_engine)
    job = await submit(client, body)
    lease = await worker.claim(database_engine)

    async def unavailable(connection, subject):
        raise OSError("identity unavailable")

    with pytest.raises(OSError):
        await worker.step(database_engine, *lease, unavailable)
    assert (await client.get(f"{BASE}/{job['job_id']}")).json()["totals"] == {"pending": 2}
    for _ in range(3):
        async with database_engine.begin() as connection:
            await connection.execute(update(jobs).values(lease_until=func.clock_timestamp()))
        await worker.claim(database_engine)
    assert (await client.get(f"{BASE}/{job['job_id']}")).json()["state"] == "failed"
    assert (await client.get(f"{BASE}/{uuid4()}")).status_code == 404
    fresh = await submit(client, body)
    async with database_engine.begin() as connection:
        row = (
            (await connection.execute(select(jobs).where(jobs.c.job_id == UUID(fresh["job_id"]))))
            .mappings()
            .one()
        )
        with pytest.raises(ValueError):
            await service.finish(connection, row, "succeeded")


async def test_atomic_finalization_database_failure_and_immutable_history(api, database_engine):
    client, actor = api
    body, _ = await setup(api, database_engine)
    job = await submit(client, body)
    lease = await worker.claim(database_engine)
    async with database_engine.begin() as connection:
        await connection.execute(
            text("""
            CREATE FUNCTION fail_job_activity() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN RAISE EXCEPTION 'Evidence storage unavailable'; END $$
        """)
        )
        await connection.execute(
            text("""
            CREATE TRIGGER fail_job_activity BEFORE INSERT ON lifecycle_activity_entries
            FOR EACH ROW EXECUTE FUNCTION fail_job_activity()
        """)
        )
    with pytest.raises(DBAPIError):
        await worker.step(database_engine, *lease, resolver(actor))
    assert (await client.get(f"{BASE}/{job['job_id']}")).json()["totals"] == {"pending": 2}
    async with database_engine.begin() as connection:
        assert await connection.scalar(select(func.count()).select_from(artifacts)) == 0
        await connection.execute(
            text("DROP TRIGGER fail_job_activity ON lifecycle_activity_entries")
        )
        await connection.execute(
            update(resources).where(resources.c.id == "resource-0").values(lock_version=2)
        )
    assert not await worker.step(database_engine, *lease, resolver(actor))
    assert (await client.get(f"{BASE}/{job['job_id']}")).json()["state"] == "partially_succeeded"
    for statement in [
        update(jobs).values(state="queued"),
        update(jobs).values(workflow_version_id=uuid4()),
        update(items).values(resource_version=3),
        update(items).values(disposition="pending"),
    ]:
        with pytest.raises(DBAPIError):
            async with database_engine.begin() as connection:
                await connection.execute(statement)


async def test_wrong_worker_identity_is_rejected_and_development_resolver(api, database_engine):
    from test_api import make_settings

    client, actor = api
    body, _ = await setup(api, database_engine)
    job = await submit(client, body)
    lease = await worker.claim(database_engine)
    actor[0] = replace(MANAGER, actor_id="wrong-subject")
    assert not await worker.step(database_engine, *lease, resolver(actor))
    assert (await client.get(f"{BASE}/{job['job_id']}")).json()["state"] == "rejected"
    with pytest.raises(RuntimeError):
        worker.development_resolver(make_settings())
    settings = replace(
        make_settings(),
        auth_mode="development",
        dev_auth_actor_id="dev",
        dev_auth_display_name="Dev",
        dev_auth_permissions=("jobs:read",),
    )
    resolve = worker.development_resolver(settings)
    assert await resolve(None, {"kind": "user", "subject_key": "other"}) is None
    assert (await resolve(None, {"kind": "user", "subject_key": "dev"})).permissions == {
        "jobs:read"
    }


async def test_separate_worker_uses_durable_grants_and_rejects_revoked_account(
    api, database_engine, monkeypatch
):
    from test_api import make_settings
    from test_identity import ADMIN, CONTEXTS, IDENTITY, command

    from app.identity import service as identity
    from app.identity.models import accounts
    from app.identity.schemas import AccountChange

    client, actor = api
    body, _ = await setup(api, database_engine)
    invitation = await identity.create_invitation(
        database_engine,
        replace(ADMIN, permissions=ADMIN.permissions | {"sets:read", "sources:read"}),
        command(set_ids=[body["set_id"]]).model_copy(
            update={
                "permissions": [
                    "sets:read",
                    "sources:read",
                    "resources:read",
                    "jobs:read",
                    "jobs:submit",
                ]
            }
        ),
        uuid4(),
    )
    session, _ = await identity.establish_session(
        database_engine, IDENTITY, invitation["token"], 3600, CONTEXTS
    )
    actor[0] = await identity.authenticate_session(database_engine, session, CONTEXTS)
    job = await submit(client, body)
    monkeypatch.setattr(worker, "get_settings", make_settings)
    monkeypatch.setattr(worker, "get_engine", lambda: database_engine)
    await worker.run(once=True)
    assert (await client.get(f"{BASE}/{job['job_id']}")).json()["state"] == "succeeded"
    job = await submit(client, body)
    async with database_engine.connect() as connection:
        target = await connection.scalar(select(accounts.c.actor_id))
    await identity.change_account(
        database_engine,
        ADMIN,
        target,
        AccountChange(permissions=[], set_ids=[], active=False, lock_version=1),
        uuid4(),
    )
    await worker.run(once=True)
    assert (await client.get(f"{BASE}/{job['job_id']}")).json()["state"] == "rejected"
    await worker.run(once=True)


async def test_saved_selection_large_job_streams_immutable_report(api, database_engine):
    from sqlalchemy import delete

    from app.jobs.models import artifact_chunks

    client, actor = api
    body, _ = await setup(api, database_engine, 1005)
    snapshot = await client.post("/api/v1/admin/resources/selections", headers=headers(), json={})
    command = {
        "set_id": body["set_id"],
        "selection_id": snapshot.json()["selection_id"],
    }
    async with database_engine.begin() as connection:
        await connection.execute(
            update(resources).where(resources.c.id == "resource-0").values(lock_version=2)
        )
    key = uuid4()
    job = await submit(client, command, key)
    assert job["totals"] == {"pending": 1005}
    assert (await submit(client, command, key))["job_id"] == job["job_id"]
    lease = await worker.claim(database_engine)
    while await worker.step(database_engine, *lease, resolver(actor)):
        pass
    report = await client.get(f"{BASE}/{job['job_id']}/report")
    assert report.status_code == 200, report.text
    assert report.json()["totals"] == {"unchanged": 1004, "conflicted": 1}
    assert len(report.json()["items"]) == 1005
    assert len(report.content) == int(report.headers["content-length"])
    assert report.headers["etag"] == '"' + hashlib.sha256(report.content).hexdigest() + '"'
    async with database_engine.connect() as connection:
        artifact = (await connection.execute(select(artifacts))).mappings().one()
        assert artifact["content"] is None
        chunks = (await connection.execute(select(artifact_chunks))).mappings().all()
        assert len(chunks) > 1 and all(len(c["content"]) <= 65536 for c in chunks)
    for statement in [
        update(artifact_chunks).values(content=b"changed"),
        delete(artifact_chunks),
        insert(artifact_chunks).values(
            artifact_id=artifact["artifact_id"], position=999, content=b"extra"
        ),
    ]:
        with pytest.raises(DBAPIError):
            async with database_engine.begin() as connection:
                await connection.execute(statement)
    async with database_engine.begin() as connection:
        await connection.execute(update(artifacts).values(expires_at=func.clock_timestamp()))
        await service.expire_artifacts(connection)
        assert await connection.scalar(select(func.count()).select_from(artifact_chunks)) == 0
    assert (await client.get(f"{BASE}/{job['job_id']}/report")).status_code == 410


async def test_saved_selection_submission_requires_owner_scope_and_exactly_one_source(
    api, database_engine
):
    client, actor = api
    body, _ = await setup(api, database_engine)
    snapshot = await client.post("/api/v1/admin/resources/selections", headers=headers(), json={})
    command = {
        "set_id": body["set_id"],
        "selection_id": snapshot.json()["selection_id"],
    }
    for invalid in [
        {"set_id": body["set_id"]},
        {**command, "selection": body["selection"]},
    ]:
        assert (await client.post(BASE, headers=headers(), json=invalid)).status_code == 422
    actor[0] = replace(MANAGER, actor_id="another-user")
    assert (await client.post(BASE, headers=headers(), json=command)).status_code == 404
    actor[0] = MANAGER
    other = await create(client, code="other-job-scope")
    assert (
        await client.post(
            BASE,
            headers=headers(),
            json={**command, "set_id": other["set_id"]},
        )
    ).status_code == 422
    empty = await client.post(
        "/api/v1/admin/resources/selections", headers=headers(), json={"q": "absent"}
    )
    assert (
        await client.post(
            BASE,
            headers=headers(),
            json={**command, "selection_id": empty.json()["selection_id"]},
        )
    ).status_code == 422
