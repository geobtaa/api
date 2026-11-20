from dataclasses import replace
from uuid import uuid4

import pytest
from sqlalchemy import select, update
from test_jobs import MANAGER, setup, submit
from test_managing_sets import api as set_api
from test_managing_sets import create, headers

from app.activity import activity
from app.resources.models import resources
from app.sets.models import sets

api = set_api
pytestmark = pytest.mark.integration


@pytest.mark.parametrize("intake_manager", [False, True])
async def test_first_assignment_scope_version_replay_and_activity(
    api, database_engine, intake_manager
):
    client, actors = api
    target = await create(client)
    target_id = target["set_id"]
    owner = replace(
        MANAGER,
        permissions=MANAGER.permissions | {"resources:create", "resources:associate"},
        set_ids=frozenset({target_id}),
    )
    actors[0] = owner
    base = "/api/v1/admin/resources"
    path = base + "/hand-drawn"
    created = await client.post(
        base, json={"id": "hand-drawn", "title": "Hand-drawn map"}, headers=headers()
    )
    assert created.status_code == 201, created.text
    draft = (await client.get(path)).json()
    assert draft["set_id"] is None and draft["source_id"] is None and draft["can_associate"]
    spec = dict(
        source_set_id=None,
        target_set_id=target_id,
        resource_version=draft["lock_version"],
        reason="Maps curated by the county",
        confirmed=True,
    )
    key = headers()

    async def assign(**changes):
        return await client.put(path + "/set", json={**spec, **changes}, headers=key)

    actors[0] = replace(owner, permissions=owner.permissions - {"resources:associate"})
    assert not (await client.get(path)).json()["can_associate"]
    assert (await assign()).status_code == 403
    actors[0] = replace(owner, set_ids=frozenset())
    assert (await assign()).status_code == 404
    stranger = replace(owner, actor_id="colleague", display_name="Colleague")
    actors[0] = stranger
    assert (await assign()).status_code == 404
    actors[0] = (
        replace(stranger, permissions=stranger.permissions | {"resources:intake-manage"})
        if intake_manager
        else owner
    )
    assert (await assign(resource_version=5)).status_code == 409
    assert (await assign(confirmed=False)).status_code == 422
    assert (await assign(reason=" ")).status_code == 422
    result = await assign()
    assert result.status_code == 200, result.text
    assert (await assign()).json() == result.json()
    saved = (await client.get(path)).json()
    assert saved["set_id"] == target_id and saved["source_id"] == target["source_id"]
    assert saved["lock_version"] == draft["lock_version"] + 1
    assert (
        saved["metadata"]["dct_title_s"] == "Hand-drawn map"
        and saved["publication_state"] == "draft"
    )
    async with database_engine.connect() as connection:
        fact = (
            (
                await connection.execute(
                    select(activity).where(activity.c.action == "resource.associated")
                )
            )
            .mappings()
            .one()
        )
        assert fact["actor_display_name"] == actors[0].display_name and fact["recorded_at"]
        assert (
            fact["set_id"] == target_id
            and fact["resource_id"] == "hand-drawn"
            and fact["reason"] == spec["reason"]
        )
        assert (
            fact["details"]["source_set_id"] is None
            and fact["details"]["previous_source_id"] is None
        )
        assert fact["details"]["lock_version"] == saved["lock_version"]
    if intake_manager:
        actors[0] = stranger
        assert (await assign()).status_code == 404
    actors[0] = replace(actors[0], set_ids=frozenset())
    assert (await assign()).status_code == 404


async def test_first_assignment_requires_draft_and_nonretired_target(api, database_engine):
    client, actors = api
    target = await create(client)
    actors[0] = replace(
        MANAGER, permissions=MANAGER.permissions | {"resources:create", "resources:associate"}
    )
    base = "/api/v1/admin/resources"
    assert (
        await client.post(base, json={"id": "map", "title": "Map"}, headers=headers())
    ).status_code == 201
    spec = dict(
        source_set_id=None,
        target_set_id=target["set_id"],
        resource_version=1,
        reason="Curate",
        confirmed=True,
    )
    async with database_engine.begin() as conn:
        await conn.execute(
            update(resources).where(resources.c.id == "map").values(publication_state="published")
        )
    assert not (await client.get(base + "/map")).json()["can_associate"]
    assert (await client.put(base + "/map/set", json=spec, headers=headers())).status_code == 409
    async with database_engine.begin() as conn:
        await conn.execute(
            update(resources).where(resources.c.id == "map").values(publication_state="draft")
        )
        await conn.execute(
            update(sets).where(sets.c.set_id == target["set_id"]).values(status="retired")
        )
    assert (await client.put(base + "/map/set", json=spec, headers=headers())).status_code == 409
    assert (await client.get(base + "/map")).json()["lock_version"] == 1


async def test_representative_and_reassignment_preserve_resource_and_evidence(api, database_engine):
    client, actor = api
    body, source = await setup(api, database_engine)
    actor[0] = replace(MANAGER, permissions=MANAGER.permissions | {"resources:associate"})
    target = await create(client, code="target-county")
    path = f"/api/v1/admin/sets/{source['set_id']}/representative"
    spec = {"resource_id": "resource-0", "lock_version": 1, "reason": "Source representative"}
    key = uuid4()
    result = await client.put(path, headers=headers(key), json=spec)
    assert result.status_code == 200, result.text
    assert result.json()["represented_by_id"] == "resource-0"
    assert (await client.put(path, headers=headers(key), json=spec)).json() == result.json()
    association = {
        "source_set_id": source["set_id"],
        "target_set_id": target["set_id"],
        "resource_version": 1,
        "reason": "Approved reassignment",
        "confirmed": True,
    }
    path2 = "/api/v1/admin/resources/resource-0/set"
    key2 = uuid4()
    result = await client.put(path2, headers=headers(key2), json=association)
    assert result.status_code == 200, result.text
    assert result.json()["lock_version"] == 2
    assert (await client.get(f"/api/v1/admin/sets/{source['set_id']}")).json()[
        "resource_count"
    ] == 1
    assert (await client.get(f"/api/v1/admin/sets/{target['set_id']}")).json()[
        "resource_count"
    ] == 1
    assert (
        await client.put(path2, headers=headers(key2), json=association)
    ).json() == result.json()
    async with database_engine.connect() as connection:
        facts = (
            (
                await connection.execute(
                    select(activity).where(activity.c.action == "resource.associated")
                )
            )
            .mappings()
            .all()
        )
        assert len(facts) == 2 and facts[0]["correlation_id"] == facts[1]["correlation_id"]
        assert {str(f["set_id"]) for f in facts} == {
            source["set_id"],
            target["set_id"],
        }
        assert all(f["resource_id"] == "resource-0" for f in facts)
    # Representation is a separate association; reassignment does not silently clear it.
    result = await client.put(
        path,
        headers=headers(),
        json={"resource_id": None, "lock_version": 2, "reason": "Clear obsolete link"},
    )
    assert result.status_code == 200 and result.json()["represented_by_id"] is None
    assert (await client.put(path2, headers=headers(), json=association)).status_code == 409
    actor[0] = replace(actor[0], set_ids=frozenset({target["set_id"]}))
    assert (await client.put(path2, headers=headers(key2), json=association)).status_code == 404
    assert body["selection"][0]["lock_version"] == 1


async def test_association_denial_validation_and_active_job_conflicts(api, database_engine):
    client, actor = api
    body, source = await setup(api, database_engine)
    actor[0] = replace(MANAGER, permissions=MANAGER.permissions | {"resources:associate"})
    target = await create(client, code="target-county")
    path = "/api/v1/admin/resources/resource-0/set"
    spec = {
        "source_set_id": source["set_id"],
        "target_set_id": target["set_id"],
        "resource_version": 1,
        "reason": "Approved",
        "confirmed": True,
    }
    assert (
        await client.put(path, headers=headers(), json={**spec, "confirmed": False})
    ).status_code == 422
    assert (
        await client.put(path, headers=headers(), json={**spec, "target_set_id": source["set_id"]})
    ).status_code == 422
    assert (
        await client.put(path, headers=headers(), json={**spec, "target_set_id": str(uuid4())})
    ).status_code == 404
    job = await submit(client, body)
    assert (await client.put(path, headers=headers(), json=spec)).status_code == 409
    assert (
        await client.post(f"/api/v1/admin/jobs/{job['job_id']}/cancel", headers=headers())
    ).status_code == 200
    actor[0] = replace(actor[0], kind="service_account")
    assert (await client.put(path, headers=headers(), json=spec)).status_code == 403
    actor[0] = replace(MANAGER, permissions=MANAGER.permissions | {"resources:associate"})
    rep = f"/api/v1/admin/sets/{source['set_id']}/representative"
    assert (
        await client.put(
            rep,
            headers=headers(),
            json={"resource_id": "missing", "lock_version": 1, "reason": "Missing"},
        )
    ).status_code == 422
    assert (
        await client.put(
            rep,
            headers=headers(),
            json={"resource_id": None, "lock_version": 1, "reason": "No change"},
        )
    ).status_code == 422
    actor[0] = replace(actor[0], set_ids=frozenset({target["set_id"]}))
    assert (
        await client.put(
            rep,
            headers=headers(),
            json={"resource_id": "resource-0", "lock_version": 1, "reason": "Denied"},
        )
    ).status_code == 404


async def test_association_evidence_failure_rolls_back_membership_and_receipt(api, database_engine):
    from sqlalchemy import text

    client, actor = api
    _, source = await setup(api, database_engine)
    actor[0] = replace(MANAGER, permissions=MANAGER.permissions | {"resources:associate"})
    target = await create(client, code="target-county")
    path = "/api/v1/admin/resources/resource-0/set"
    spec = {
        "source_set_id": source["set_id"],
        "target_set_id": target["set_id"],
        "resource_version": 1,
        "reason": "Approved",
        "confirmed": True,
    }
    async with database_engine.begin() as connection:
        await connection.execute(
            text("""CREATE FUNCTION fail_association() RETURNS trigger
            LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Evidence unavailable'; END $$""")
        )
        await connection.execute(
            text("""CREATE TRIGGER fail_association BEFORE INSERT ON
            lifecycle_activity_entries FOR EACH ROW EXECUTE FUNCTION fail_association()""")
        )
    key = uuid4()
    assert (await client.put(path, headers=headers(key), json=spec)).status_code == 503
    assert (await client.get(f"/api/v1/admin/sets/{source['set_id']}")).json()[
        "resource_count"
    ] == 2
    async with database_engine.begin() as connection:
        await connection.execute(
            text("DROP TRIGGER fail_association ON lifecycle_activity_entries")
        )
    assert (await client.put(path, headers=headers(key), json=spec)).status_code == 200
    assert (await client.get(f"/api/v1/admin/sets/{source['set_id']}")).json()[
        "resource_count"
    ] == 1
