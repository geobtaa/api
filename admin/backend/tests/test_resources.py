import asyncio
import json
from dataclasses import replace
from uuid import uuid4

import httpx2
import pytest
from sqlalchemy import func, select, text
from test_api import make_settings
from test_managing_sets import EDITOR, create, headers

from app.activity import activity
from app.fixtures import load_catalog
from app.main import create_app
from app.resources.models import distribution_types, distributions, evidence, imports, resources
from app.resources.validation import VOCABULARY
from app.sets.models import sets
from app.url_ids import encode_id

pytestmark = pytest.mark.integration
BASE = "/api/v1/admin/resources"


@pytest.fixture
async def api(database_engine):
    actor = [
        replace(EDITOR, permissions=EDITOR.permissions | {"resources:read", "resources:import"})
    ]

    async def authenticate(_):
        return actor[0]

    app = create_app(authenticator=authenticate, settings=make_settings())
    app.state.database_engine = database_engine
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client, actor


async def preview(client, scope, records):
    payload = {"set_id": scope["set_id"], "records": records}
    response = await client.post(BASE + "/imports/preview", headers=headers(), json=payload)
    assert response.status_code == 200, response.text
    return {
        **payload,
        "preview_hash": response.json()["preview_hash"],
        "confirmed": True,
    }, response.json()


async def test_fixture_import_persists_drafts_links_and_activity_atomically(api, database_engine):
    client, _ = api
    scope = await create(client)
    records = [item.metadata for item in load_catalog().items]
    payload, plan = await preview(client, scope, records)
    assert plan["ready"] == 13, plan
    key = uuid4()
    result = await client.post(BASE + "/imports", headers=headers(key), json=payload)
    assert result.status_code == 200, result.text
    assert result.json()["created"] == 13
    async with database_engine.connect() as connection:
        assert await connection.scalar(select(func.count()).select_from(resources)) == 13
        assert await connection.scalar(select(func.count()).select_from(evidence)) == 13
        assert await connection.scalar(select(func.count()).select_from(imports)) == 1
        assert (
            await connection.scalar(
                select(func.count())
                .select_from(activity)
                .where(activity.c.action == "resources.imported")
            )
            == 1
        )
        assert await connection.scalar(select(func.count()).select_from(distributions)) > 14
        vocab = (
            await connection.execute(
                select(distribution_types.c.id, distribution_types.c.uri).order_by(
                    distribution_types.c.id
                )
            )
        ).all()
        assert vocab == [(row["id"], row["uri"]) for row in VOCABULARY]
    replay = await client.post(BASE + "/imports", headers=headers(key), json=payload)
    assert replay.json() == result.json()
    page = (await client.get(BASE, params={"limit": 2})).json()
    assert page["total"] == 13 and len(page["items"]) == 2
    assert all(row["publication_state"] == "draft" for row in page["items"])
    identifier = records[0]["id"]
    detail = (await client.get(BASE + "/" + encode_id(identifier), params={})).json()
    assert detail["source_record"] == records[0]
    assert detail["metadata"]["b1g_publication_state_s"] == "draft"
    assert detail["metadata"]["id"] == identifier
    assert detail["import_warnings"]
    assert (await client.get(BASE, params={"q": identifier})).json()["total"] == 1
    assert (await client.get(BASE, params={"q": "%"})).json()["total"] == 0
    assert (await client.get(BASE, params={"set_id": str(uuid4())})).json()["items"] == []
    assert (await client.get(BASE + "/" + encode_id("absent"), params={})).status_code == 404
    assert (await client.get("/api/v1/admin/sets/" + scope["set_id"] + "/activity")).json()[
        "total"
    ] == 2
    _, duplicate = await preview(client, scope, records)
    assert sum(row["outcome"] == "skipped" for row in duplicate["items"]) == 13
    assert sum(row["outcome"] == "invalid" for row in duplicate["items"]) == 1


async def test_partial_batch_and_unknown_reference_evidence(api, database_engine):
    client, _ = api
    scope = await create(client)
    rows = [
        {
            "id": "valid",
            "dct_title_s": "A valid draft",
            "gbl_suppressed_b": False,
            "gbl_indexYear_im": [0],
            "dct_description_sm": [],
            "dct_references_s": json.dumps(
                {
                    "https://example.org/unknown": "https://example.org/data",
                    "http://schema.org/downloadUrl": [
                        {"url": "https://example.org/a", "label": "A"},
                        {"url": "https://example.org/b"},
                    ],
                }
            ),
        },
        {"id": "bad", "dct_title_s": "Bad", "dct_description_sm": "wrong"},
        {"id": "dupe", "dct_title_s": "One"},
        {"id": "dupe", "dct_title_s": "Two"},
    ]
    payload, plan = await preview(client, scope, rows)
    assert plan["ready"] == 1
    assert [r["outcome"] for r in plan["items"]] == ["ready", "invalid", "invalid", "invalid"]
    response = await client.post(BASE + "/imports", headers=headers(), json=payload)
    assert response.json()["created"] == 1
    detail = (await client.get(BASE + "/" + encode_id("valid"), params={})).json()
    assert detail["metadata"]["gbl_suppressed_b"] is False
    assert detail["metadata"]["gbl_indexYear_im"] == [0]
    assert detail["metadata"]["dct_description_sm"] == []
    assert detail["source_record"] == rows[0]
    refs = json.loads(detail["metadata"]["dct_references_s"])
    assert len(refs["http://schema.org/downloadUrl"]) == 2
    assert "unknown" not in refs


async def test_stale_preview_retry_collision_and_competing_imports(api, database_engine):
    client, _ = api
    scope = await create(client)
    payload, _ = await preview(client, scope, [{"id": "one", "dct_title_s": "First"}])
    key = uuid4()
    first, second = await asyncio.gather(
        *[client.post(BASE + "/imports", headers=headers(key), json=payload) for _ in range(2)]
    )
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert (
        await client.post(BASE + "/imports", headers=headers(), json=payload)
    ).status_code == 409
    changed = {**payload, "records": [{"id": "one", "dct_title_s": "Changed"}]}
    assert (
        await client.post(BASE + "/imports", headers=headers(key), json=changed)
    ).status_code == 409
    assert (await client.get(BASE + "/" + encode_id("one"), params={})).json()["metadata"][
        "dct_title_s"
    ] == "First"
    assert (
        await client.post(
            BASE + "/imports", headers=headers(), json={**payload, "confirmed": False}
        )
    ).status_code == 422
    async with database_engine.connect() as connection:
        assert await connection.scalar(select(func.count()).select_from(resources)) == 1


async def test_authorization_scope_and_replay_rechecked(api, database_engine):
    client, actor = api
    scope = await create(client)
    original = actor[0]
    payload, _ = await preview(client, scope, [{"id": "scoped", "dct_title_s": "Scoped"}])
    key = uuid4()
    assert (
        await client.post(BASE + "/imports", headers=headers(key), json=payload)
    ).status_code == 200
    actor[0] = replace(original, set_ids=frozenset())
    assert (await client.get(BASE)).json()["total"] == 0
    assert (await client.get(BASE + "/" + encode_id("scoped"), params={})).status_code == 404
    assert (
        await client.post(BASE + "/imports", headers=headers(key), json=payload)
    ).status_code == 404
    actor[0] = replace(original, set_ids=frozenset({scope["set_id"]}))
    assert (await client.get(BASE)).json()["total"] == 1
    actor[0] = replace(original, kind="service_account")
    assert (
        await client.post(
            BASE + "/imports/preview",
            headers=headers(),
            json={"set_id": scope["set_id"], "records": []},
        )
    ).status_code == 422
    valid = {
        "set_id": scope["set_id"],
        "records": [{"id": "x", "dct_title_s": "X"}],
    }
    assert (
        await client.post(BASE + "/imports/preview", headers=headers(), json=valid)
    ).status_code == 403
    actor[0] = replace(original, permissions=frozenset())
    assert (await client.get(BASE)).status_code == 403
    actor[0] = None
    assert (await client.get(BASE)).status_code == 401
    actor[0] = original
    assert (await client.post(BASE + "/imports/preview", json=valid)).status_code == 422
    async with database_engine.begin() as connection:
        await connection.execute(sets.update().values(status="retired"))
    assert (
        await client.post(BASE + "/imports/preview", headers=headers(), json=valid)
    ).status_code == 409


async def test_import_rolls_back_when_activity_fails(api, database_engine):
    client, _ = api
    scope = await create(client)
    payload, _ = await preview(client, scope, [{"id": "rollback", "dct_title_s": "Rollback"}])
    async with database_engine.begin() as connection:
        await connection.execute(
            text(
                """CREATE FUNCTION reject_import() RETURNS trigger LANGUAGE plpgsql AS $$
                BEGIN IF NEW.action = 'resources.imported' THEN
                    RAISE EXCEPTION 'test failure';
                END IF; RETURN NEW; END $$"""
            )
        )
        await connection.execute(
            text(
                "CREATE TRIGGER reject_import BEFORE INSERT ON lifecycle_activity_entries "
                "FOR EACH ROW EXECUTE FUNCTION reject_import()"
            )
        )
    key = uuid4()
    assert (
        await client.post(BASE + "/imports", headers=headers(key), json=payload)
    ).status_code == 503
    async with database_engine.begin() as connection:
        for table in [resources, imports, evidence, distributions]:
            assert await connection.scalar(select(func.count()).select_from(table)) == 0
        await connection.execute(text("DROP TRIGGER reject_import ON lifecycle_activity_entries"))
    assert (await client.post(BASE + "/imports", headers=headers(key), json=payload)).json()[
        "created"
    ] == 1


async def test_import_keeps_managing_set_and_does_not_complete_maintenance(api, database_engine):
    client, actor = api
    actor[0] = replace(
        actor[0],
        permissions=actor[0].permissions
        | {
            "tasks:read",
            "tasks:create",
            "work:configure",
        },
    )
    subject = await create(client, set_id="native-string-set")
    rule = await client.put(
        f"/api/v1/admin/sets/{subject['set_id']}/maintenance/ingest",
        headers=headers(),
        json={"lock_version": 0, "interval": "P1M", "next_due_on": "2026-09-23"},
    )
    assert rule.status_code == 200, rule.text
    before = (await client.get("/api/v1/admin/tasks")).json()
    payload, _ = await preview(client, subject, [{"id": "new-map", "dct_title_s": "Map"}])
    result = await client.post(BASE + "/imports", headers=headers(), json=payload)
    assert result.status_code == 200, result.text
    assert (await client.get("/api/v1/admin/tasks")).json() == before
    saved = (await client.get(BASE + "/new-map")).json()
    assert saved["set_id"] == "native-string-set"
    assert "lifecycle_id" not in saved and "lifecycle_id" not in saved["metadata"]
    async with database_engine.connect() as connection:
        row = (await connection.execute(select(resources.c.set_id, resources.c.lifecycle_id))).one()
        assert tuple(row) == ("native-string-set", None)


async def test_create_manual_draft_and_retry_without_import(api, database_engine):
    client, actor = api
    actor[0] = replace(
        actor[0], permissions=frozenset({"resources:create", "resources:read", "resources:update"})
    )
    payload = {"id": "new", "title": "Hand-drawn map", "description": "County boundaries"}
    key = headers()
    first, second = await asyncio.gather(
        *[client.post(BASE, headers=key, json=payload) for _ in range(2)]
    )
    assert first.status_code == second.status_code == 201, first.text
    location = first.headers["location"]
    assert location == BASE + "/" + encode_id("new")
    draft = (await client.get(location)).json()
    assert draft["publication_state"] == "draft" and draft["lock_version"] == 1
    assert draft["set_id"] is draft["source_id"] is draft["source_record"] is None
    assert draft["metadata"]["gbl_mdVersion_s"] == "Aardvark"
    assert draft["metadata"]["dct_description_sm"] == ["County boundaries"]
    assert draft["editable"]
    for h in [key, headers()]:
        conflict = await client.post(BASE, headers=h, json={**payload, "title": "Overwrite"})
        assert conflict.status_code == 409
    assert (
        await client.patch(
            location,
            headers=headers(),
            json={"lock_version": 1, "values": {"dct_title_s": "Updated"}},
        )
    ).status_code == 200
    assert (await client.get(location + "/metadata")).json()["dct_title_s"] == "Updated"
    async with database_engine.connect() as connection:
        event = (
            (
                await connection.execute(
                    select(activity).where(activity.c.action == "resource.created")
                )
            )
            .mappings()
            .one()
        )
        assert event["set_id"] is None and event["resource_id"] == "new"
        assert await connection.scalar(select(func.count()).select_from(imports)) == 0
        assert await connection.scalar(select(func.count()).select_from(evidence)) == 0
    actor[0] = replace(actor[0], actor_id="other")
    assert (await client.get(location)).status_code == 404
    assert (await client.get(BASE)).json()["total"] == 0
    actor[0] = replace(actor[0], permissions=actor[0].permissions | {"resources:intake-manage"})
    assert (await client.get(location)).status_code == 200


async def test_manual_creation_checks_scope_grants_and_input(api, database_engine):
    client, actor = api
    scope = await create(client)
    payload = {"id": "map/1", "title": "Maps", "set_id": scope["set_id"]}
    key = headers()
    assert not (await client.get(BASE)).json()["can_create"]
    assert (await client.post(BASE, json=payload, headers=key)).status_code == 403
    staff = replace(actor[0], permissions=actor[0].permissions | {"resources:create"})
    actor[0] = replace(staff, kind="service_account")
    assert (await client.post(BASE, json=payload, headers=key)).status_code == 403
    actor[0] = replace(staff, set_ids=frozenset())
    assert (await client.post(BASE, json=payload, headers=key)).status_code == 404
    actor[0] = staff
    assert (await client.get(BASE)).json()["can_create"]
    assert (await client.post(BASE, json=payload)).status_code == 422
    for changes in (
        {"title": " "},
        {"publication_state": "published"},
        {"id": "x\n"},
        {"description": "x\x00"},
    ):
        assert (
            await client.post(BASE, json={**payload, **changes}, headers=key)
        ).status_code == 422
    result = await client.post(BASE, json=payload, headers=key)
    assert result.status_code == 201, result.text
    detail = (await client.get(result.headers["location"])).json()
    assert detail["source_id"] == scope["source_id"] and detail["set_id"] == scope["set_id"]
    actor[0] = replace(staff, set_ids=frozenset())
    assert (await client.post(BASE, json=payload, headers=key)).status_code == 404
    actor[0] = staff
    async with database_engine.begin() as connection:
        await connection.execute(
            sets.update().where(sets.c.set_id == scope["set_id"]).values(status="retired")
        )
    assert (
        await client.post(BASE, json={**payload, "id": "other"}, headers=headers())
    ).status_code == 409


async def test_manual_creation_rolls_back_if_activity_cannot_commit(api, database_engine):
    client, actor = api
    actor[0] = replace(actor[0], permissions=actor[0].permissions | {"resources:create"})
    payload = {"id": "rollback", "title": "Test"}
    key = headers()
    async with database_engine.begin() as conn:
        await conn.execute(
            text(
                "ALTER TABLE lifecycle_activity_entries ADD CONSTRAINT reject_creation "
                "CHECK (action <> 'resource.created')"
            )
        )

    assert (await client.post(BASE, json=payload, headers=key)).status_code == 503
    assert (await client.get(BASE + "/rollback")).status_code == 404
    async with database_engine.begin() as conn:
        await conn.execute(
            text("ALTER TABLE lifecycle_activity_entries DROP CONSTRAINT reject_creation")
        )
    assert (await client.post(BASE, json=payload, headers=key)).status_code == 201
