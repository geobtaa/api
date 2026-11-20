import asyncio
from dataclasses import replace
from uuid import uuid4

import pytest
import test_resources
from sqlalchemy import event, func, select, text, update
from test_managing_sets import create, headers
from test_resources import BASE, preview

from app.activity import activity
from app.resources.models import distributions, evidence, resources
from app.sets.models import commands, sets
from app.url_ids import encode_id

api = test_resources.api
pytestmark = pytest.mark.integration


async def seed(api):
    client, actor = api
    actor[0] = replace(actor[0], permissions=actor[0].permissions | {"resources:update"})
    scope = await create(client)
    record = {
        "id": "editor/test",
        "dct_title_s": "Original title",
        "schema_provider_s": "Provider",
        "dct_description_sm": ["One", "Two"],
        "gbl_mdVersion_s": "1.0",
        "gbl_indexYear_im": [1900],
        "dct_references_s": '{"http://schema.org/url":"https://example.org/original"}',
    }
    payload, _ = await preview(client, scope, [record])
    assert (await client.post(BASE + "/imports", headers=headers(), json=payload)).json()[
        "created"
    ] == 1
    return client, actor, scope, record


async def patch(client, body, key=None):
    return await client.patch(
        BASE + "/" + encode_id("editor/test"), params={}, headers=headers(key), json=body
    )


async def test_edit_rechecks_owner_after_waiting_for_set_lock(api, database_engine):
    client, _, origin, _ = await seed(api)
    target = await create(client, set_id="new-manager")
    waiting = asyncio.Event()

    def locking_set(connection, cursor, statement, parameters, context, executemany):
        if "FROM sets" in statement and "FOR UPDATE" in statement:
            waiting.set()

    event.listen(database_engine.sync_engine, "before_cursor_execute", locking_set)
    pending = None
    try:
        async with database_engine.begin() as connection:
            await connection.execute(
                select(sets).where(sets.c.set_id == origin["set_id"]).with_for_update()
            )
            waiting.clear()
            pending = asyncio.create_task(
                patch(client, {"lock_version": 1, "values": {"dct_title_s": "Stale edit"}})
            )
            await asyncio.wait_for(waiting.wait(), timeout=5)
            assert not pending.done()
            # Simulate a reassignment which committed after the edit's first scope read.
            await connection.execute(
                update(resources)
                .where(resources.c.id == "editor/test")
                .values(set_id=target["set_id"], lock_version=2)
            )
        result = await asyncio.wait_for(pending, timeout=5)
        assert result.status_code == 409
        assert result.json()["detail"]["code"] == "stale_version"
    finally:
        event.remove(database_engine.sync_engine, "before_cursor_execute", locking_set)
        if pending is not None and not pending.done():
            pending.cancel()
            await asyncio.gather(pending, return_exceptions=True)
    async with database_engine.connect() as connection:
        assert await connection.scalar(select(resources.c.dct_title_s)) == "Original title"
        assert await connection.scalar(select(resources.c.set_id)) == target["set_id"]
        assert (
            await connection.scalar(
                select(func.count())
                .select_from(activity)
                .where(activity.c.action == "resource.updated")
            )
            == 0
        )


async def test_selective_edit_explicit_clears_and_receipts(api, database_engine):
    client, _, scope, record = await seed(api)
    contract = (await client.get("/api/v1/admin/contracts/resources")).json()
    assert contract["can_update"] and len(contract["fields"]) > 40
    assert len(contract["distribution_types"]) == 27
    assert not {"id", "publication_state", "b1g_adminNote_sm"} & {
        field["name"] for field in contract["fields"]
    }
    body = {
        "lock_version": 1,
        "values": {
            "dct_title_s": "Updated title",
            "dct_description_sm": [],
            "gbl_georeferenced_b": False,
            "gbl_indexYear_im": [0],
        },
        "clear_fields": ["schema_provider_s"],
    }
    key = uuid4()
    saved = await patch(client, body, key)
    assert saved.status_code == 200, saved.text
    result = saved.json()
    assert result["lock_version"] == 2 and result["editable"]
    assert result["metadata"]["dct_title_s"] == "Updated title"
    assert result["metadata"]["dct_description_sm"] == []
    assert result["metadata"]["gbl_georeferenced_b"] is False
    assert result["metadata"]["gbl_indexYear_im"] == [0]
    assert "schema_provider_s" not in result["metadata"]
    assert result["metadata"]["gbl_mdVersion_s"] == "1.0"
    assert result["source_record"] == record
    assert result["distributions"][0]["url"] == "https://example.org/original"
    assert (await patch(client, body, key)).json() == result
    assert (
        await patch(client, {**body, "values": {"dct_title_s": "Different"}}, key)
    ).status_code == 409
    assert (await patch(client, body)).status_code == 409
    async with database_engine.connect() as connection:
        assert (
            await connection.scalar(
                select(func.count())
                .select_from(activity)
                .where(activity.c.action == "resource.updated")
            )
            == 1
        )
        assert await connection.scalar(select(evidence.c.source_record)) == record
    assert (await client.get("/api/v1/admin/sets/" + scope["set_id"] + "/activity")).json()[
        "total"
    ] == 3


async def test_structured_distributions_order_and_clear(api, database_engine):
    client, _, _, _ = await seed(api)
    links = [
        {"distribution_type_id": 8, "url": "https://example.org/download", "label": "Data"},
        {"distribution_type_id": 7, "url": "https://example.org/page", "label": None},
    ]
    saved = await patch(client, {"lock_version": 1, "distributions": links})
    assert saved.status_code == 200, saved.text
    assert saved.json()["distributions"] == links
    assert (await patch(client, {"lock_version": 2, "distributions": links})).status_code == 422
    async with database_engine.begin() as conn:
        original_id = await conn.scalar(
            update(distributions)
            .where(distributions.c.url == links[0]["url"])
            .values(import_id="upstream-42")
            .returning(distributions.c.id)
        )
    reversed_links = list(reversed(links))
    assert (await patch(client, {"lock_version": 2, "distributions": reversed_links})).json()[
        "distributions"
    ] == reversed_links
    async with database_engine.connect() as conn:
        assert (
            await conn.scalar(
                select(distributions.c.import_id).where(distributions.c.id == original_id)
            )
            == "upstream-42"
        )
    assert (await patch(client, {"lock_version": 3, "distributions": []})).json()[
        "distributions"
    ] == []
    async with database_engine.connect() as connection:
        assert await connection.scalar(select(func.count()).select_from(distributions)) == 0


@pytest.mark.parametrize(
    "changes",
    [
        {"values": {"id": "new-id"}},
        {"values": {"b1g_adminNote_sm": ["operational"]}},
        {"values": {"schema_provider_s": "X"}, "clear_fields": ["schema_provider_s"]},
        {"clear_fields": ["dct_title_s"]},
        {"values": {"dct_title_s": " "}},
        {"values": {"schema_provider_s": "  "}},
        {"values": {"dct_description_sm": ["  "]}},
        {"values": {"dct_description_sm": None}},
        {"values": {"dct_accessRights_s": "Unknown"}},
        {"values": {"dct_description_sm": "not an array"}},
        {"distributions": None},
        {"distributions": [{"distribution_type_id": 999, "url": "https://example.org"}]},
        {"distributions": [{"distribution_type_id": 7, "url": "https://example.org"}] * 2},
        {"distributions": [{"distribution_type_id": 7, "url": "javascript:alert(1)"}]},
        {"distributions": [{"distribution_type_id": 7, "url": "https://user:secret@example.org"}]},
        {"values": {}},
        {"values": {"dct_title_s": "Original title"}},
    ],
)
async def test_invalid_edits_do_not_write(api, database_engine, changes):
    client, _, _, _ = await seed(api)
    result = await patch(client, {"lock_version": 1, **changes})
    assert result.status_code == 422, result.text
    async with database_engine.connect() as connection:
        assert await connection.scalar(select(resources.c.lock_version)) == 1


async def test_edit_access_scope_and_read_only_states(api, database_engine):
    client, actor, _, _ = await seed(api)
    original = actor[0]
    body = {"lock_version": 1, "values": {"dct_title_s": "Updated"}}
    actor[0] = replace(original, permissions=original.permissions - {"resources:update"})
    assert not (await client.get("/api/v1/admin/contracts/resources")).json()["can_update"]
    assert (await patch(client, body)).status_code == 403
    actor[0] = replace(original, set_ids=frozenset())
    assert (await patch(client, body)).status_code == 404
    actor[0] = replace(original, kind="service_account")
    assert (await patch(client, body)).status_code == 403
    actor[0] = original
    async with database_engine.begin() as connection:
        await connection.execute(update(resources).values(publication_state="published"))
    assert (await patch(client, body)).status_code == 409
    async with database_engine.begin() as connection:
        await connection.execute(update(resources).values(publication_state="draft"))
        await connection.execute(update(sets).values(status="retired"))
    assert (await patch(client, body)).status_code == 409
    assert not (await client.get(BASE + "/" + encode_id("editor/test"), params={})).json()[
        "editable"
    ]


async def test_concurrent_edit_and_atomic_activity_rollback(api, database_engine):
    client, _, _, _ = await seed(api)
    results = await asyncio.gather(
        patch(client, {"lock_version": 1, "values": {"dct_title_s": "A"}}),
        patch(client, {"lock_version": 1, "values": {"dct_title_s": "B"}}),
    )
    assert sorted(result.status_code for result in results) == [200, 409]
    async with database_engine.begin() as connection:
        await connection.execute(
            text("""CREATE FUNCTION reject_edit() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN IF NEW.action = 'resource.updated' THEN RAISE EXCEPTION 'test failure';
            END IF; RETURN NEW; END $$""")
        )
        await connection.execute(
            text(
                "CREATE TRIGGER reject_edit BEFORE INSERT ON lifecycle_activity_entries "
                "FOR EACH ROW EXECUTE FUNCTION reject_edit()"
            )
        )
    key = uuid4()
    body = {"lock_version": 2, "values": {"dct_title_s": "Rollback"}, "distributions": []}
    assert (await patch(client, body, key)).status_code == 503
    async with database_engine.begin() as connection:
        assert await connection.scalar(select(resources.c.lock_version)) == 2
        assert await connection.scalar(select(func.count()).select_from(distributions)) == 1
        assert (
            await connection.scalar(
                select(func.count())
                .select_from(commands)
                .where(commands.c.operation.like("resource:%"))
            )
            == 1
        )
        await connection.execute(text("DROP TRIGGER reject_edit ON lifecycle_activity_entries"))
    assert (await patch(client, body, key)).json()["lock_version"] == 3


async def test_edit_key_cannot_be_reused_for_another_resource(api):
    client, _, scope, record = await seed(api)
    payload, _ = await preview(client, scope, [{**record, "id": "editor/other"}])
    assert (
        await client.post(BASE + "/imports", headers=headers(), json=payload)
    ).status_code == 200
    key = uuid4()
    body = {"lock_version": 1, "values": {"dct_title_s": "Updated"}}
    assert (await patch(client, body, key)).status_code == 200
    result = await client.patch(
        BASE + "/" + encode_id("editor/other"), params={}, headers=headers(key), json=body
    )
    assert result.status_code == 409
    assert result.json()["detail"]["code"] == "idempotency_conflict"
    assert (await client.get(BASE + "/" + encode_id("editor/other"), params={})).json()[
        "lock_version"
    ] == 1


def test_editor_contract_separates_rights_and_relationships():
    from app.auth import Actor
    from app.resources.editor import contract

    actor = Actor("staff", "user", "Staff", None, frozenset({"resources:read"}))
    result = contract(actor)
    groups = {
        section: {field["name"] for field in result["fields"] if field["section"] == section}
        for section in result["sections"]
    }
    assert "Rights & relationships" not in groups
    assert groups["Rights"] == {
        "dct_accessRights_s",
        "dct_rights_sm",
        "dct_rightsHolder_sm",
        "dct_license_sm",
    }
    assert groups["Relationships"] == {
        "dct_relation_sm",
        "pcdm_memberOf_sm",
        "dct_isPartOf_sm",
        "dct_source_sm",
        "dct_isVersionOf_sm",
        "dct_replaces_sm",
        "dct_isReplacedBy_sm",
    }
    assert {"dct_identifier_sm", "gbl_fileSize_s", "gbl_wxsIdentifier_s"} <= groups[
        "Additional metadata"
    ]


@pytest.mark.parametrize("legacy_gaps", [False, True])
async def test_published_preview_confirmation_and_pending_projection(
    api, database_engine, legacy_gaps
):
    from datetime import date

    from app.resources.editor import wait_for_public_read
    from app.resources.models import projection_requests

    client, actors, _, record = await seed(api)
    path = BASE + "/" + encode_id(record["id"])
    async with database_engine.begin() as conn:
        await conn.execute(
            update(resources)
            .where(resources.c.id == record["id"])
            .values(
                publication_state="published",
                b1g_publication_state_s="published",
                dct_language_sm=["English"],
                dct_accessRights_s="Public",
                dct_license_sm=["license"],
                b1g_code_s="test",
                b1g_dct_accrualMethod_s="Manual",
                b1g_dateAccessioned_s=date.today(),
                b1g_language_sm=None if legacy_gaps else ["English"],
            )
        )
    body = {"lock_version": 1, "values": {"dct_title_s": "Published edit"}}
    assert (
        await client.post(path + "/published-edits/preview", headers=headers(), json=body)
    ).status_code == 403
    actors[0] = replace(actors[0], permissions=actors[0].permissions | {"resources:edit-published"})
    assert (await client.patch(path, headers=headers(), json=body)).status_code == 409
    removed = {**body, "clear_fields": ["dct_license_sm"]}
    rejected = await client.post(path + "/published-edits/preview", headers=headers(), json=removed)
    assert rejected.status_code == 422
    if legacy_gaps:
        repaired = {**body, "values": {"b1g_language_sm": ["English"]}}
        improved = await client.post(
            path + "/published-edits/preview", headers=headers(), json=repaired
        )
        assert improved.status_code == 200, improved.text
    preview = await client.post(path + "/published-edits/preview", headers=headers(), json=body)
    assert preview.status_code == 200, preview.text
    assert preview.json()["changes"]["dct_title_s"]["after"] == "Published edit"
    confirm = {"edit": body, "confirmed": True, "preview_id": preview.json()["preview_id"]}
    mismatch = {**confirm, "edit": {**body, "values": {"dct_title_s": "Different"}}}
    assert (
        await client.post(path + "/published-edits", headers=headers(), json=mismatch)
    ).status_code == 409
    key = headers()
    for _ in range(2):
        saved = await client.post(path + "/published-edits", headers=key, json=confirm)
        assert saved.status_code == 200, saved.text
        assert saved.json()["lock_version"] == 2
        assert saved.json()["projection_status"] == "pending"
    async with database_engine.begin() as conn:
        assert await conn.scalar(select(func.count()).select_from(projection_requests)) == 1
    result = await wait_for_public_read(database_engine, saved.json(), timeout=0.1)
    assert result.projection_status == "pending"
    async with database_engine.begin() as conn:
        await conn.execute(update(projection_requests).values(visible_at=func.now()))
    result = await wait_for_public_read(database_engine, saved.json())
    assert result.projection_status == "live"
    newer = {**saved.json(), "lock_version": 3}
    assert (await wait_for_public_read(database_engine, newer)).projection_status == "pending"
    actors[0] = replace(actors[0], set_ids=frozenset())
    assert (
        await client.post(path + "/published-edits", headers=key, json=confirm)
    ).status_code == 404
