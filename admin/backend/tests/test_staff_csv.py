"""Staff workflows for Source, Set, Resource and Distribution exchange."""

import csv
import io
from dataclasses import replace
from uuid import uuid4

import pytest
import test_resources
from sqlalchemy import func, select, update
from test_managing_sets import create, headers
from test_resource_csv import document, resource_upload
from test_resource_editor import seed
from test_resources import BASE

from app.activity import activity
from app.resources.distribution_csv import COLUMNS
from app.resources.models import distributions, resources
from app.sources import service as source_service

api = test_resources.api
pytestmark = pytest.mark.integration
RESOURCE = BASE + "/csv"
SOURCE = "/api/v1/admin/sources/csv"
SET = "/api/v1/admin/sets/csv"


async def preview(client, base, mode, source, **scope):
    if base == RESOURCE and mode not in {"add_links", "replace_links"}:
        source = await resource_upload(client, source, mode)
    payload = {**({"mode": mode} if mode else {}), "csv": source, **scope}
    response = await client.post(base + "/preview", headers=headers(), json=payload)
    assert response.status_code == 200, response.text
    report = response.json()
    return {**payload, "preview_hash": report["preview_hash"], "confirmed": True}, report


async def apply(client, base, payload, key=None, status=200):
    response = await client.post(base + "/import", headers=headers(key), json=payload)
    assert response.status_code == status, response.text
    return response.json()


async def test_catalog_create_export_edit_replay_and_scope(api):
    client, actors = api
    staff = replace(
        actors[0], permissions=actors[0].permissions | {"sources:create", "sources:update"}
    )
    actors[0] = staff
    for base, name, csv_text in [
        (SOURCE, "source_id", "source_id,title,description\nCampus,=Campus,Historical"),
        (SET, "set_id", "set_id,source_id,title,description\nMaps,Campus,Maps,Historical"),
    ]:
        body, report = await preview(client, base, "create", csv_text)
        assert report["ready"] == 1
        key = uuid4()
        applied = await apply(client, base, body, key)
        assert applied["items"][0]["outcome"] == "created"
        assert await apply(client, base, body, key) == applied
        template = await client.get(base + "/template")
        exported = await client.get(base + "/export")
        assert template.text.splitlines()[0] == exported.text.splitlines()[0]
        exported_row = next(csv.DictReader(io.StringIO(exported.text)))
        if base == SOURCE:
            assert exported_row["title"] == "'=Campus"
        _, same = await preview(client, base, "update", exported.text)
        assert same["items"][0]["outcome"] == "unchanged"
        identifier = exported_row[name]
        body, report = await preview(
            client,
            base,
            "update",
            document(
                [name, "lock_version", "description__clear", "title"],
                [identifier, "1", "true", "Renamed"],
            ),
        )
        assert report["items"][0]["clear_fields"] == ["description"]
        assert report["items"][0]["changes"]["description"] == {"before": "Historical", "after": ""}
        key = uuid4()
        applied = await apply(client, base, body, key)
        assert applied["items"][0]["outcome"] == "updated"
        assert await apply(client, base, body, key) == applied
        await apply(client, base, body, status=409)
        if base == SET:
            actors[0] = replace(staff, set_ids=frozenset())
            assert len((await client.get(base + "/export")).text.splitlines()) == 1
            await apply(client, base, body, key, status=403)
            actors[0] = staff
    _, invalid = await preview(
        client, SET, "update", "set_id,source_id,lock_version,title\nMaps,Other,2,X"
    )
    assert "immutable" in invalid["items"][0]["errors"][0]
    _, invalid = await preview(client, SET, "create", "set_id,source_id,title\nOther,missing,X")
    assert invalid["ready"] == 0
    actors[0] = replace(staff, permissions=staff.permissions - {"sources:update"})
    assert (
        await client.post(
            SOURCE + "/preview",
            headers=headers(),
            json={"mode": "update", "csv": "source_id\nCampus"},
        )
    ).status_code == 403


async def test_catalog_validation_and_atomic_failure(api, monkeypatch, database_engine):
    client, actors = api
    actors[0] = replace(actors[0], permissions=actors[0].permissions | {"sources:create"})
    body, report = await preview(
        client, SOURCE, "create", "source_id,title\na,A\nb,B\nx,first\nx,second\ny,    "
    )
    assert [r["outcome"] for r in report["items"]] == [
        "create",
        "create",
        "invalid",
        "invalid",
        "invalid",
    ]
    original = source_service.write_activity

    async def fail_second(connection, actor, actor_id, source_id, *args, **kwargs):
        if source_id == "b":
            from app.domain import DomainError

            raise DomainError(503, "failed", "Simulated evidence failure")
        return await original(connection, actor, actor_id, source_id, *args, **kwargs)

    monkeypatch.setattr(source_service, "write_activity", fail_second)
    key = uuid4()
    await apply(client, SOURCE, body, key, status=503)
    async with database_engine.connect() as db:
        for table in (source_service.sources, source_service.commands, activity):
            assert await db.scalar(select(func.count()).select_from(table)) == 0
    monkeypatch.setattr(source_service, "write_activity", original)
    assert (await apply(client, SOURCE, body, key))["ready"] == 2


async def test_multi_set_updates_versions_visibility_and_replay(api, database_engine):
    client, actors, first, _ = await seed(api)
    second = await create(client)
    new, _ = await preview(
        client, RESOURCE, "create", "ID,Title\nother,Other", set_id=second["set_id"]
    )
    await apply(client, RESOURCE, new)
    source = "ID,Lock Version,Title\neditor/test,1,A\nother,1,B\nmissing,1,C"
    body, report = await preview(client, RESOURCE, "update", source)
    assert [r["set_id"] for r in report["items"]] == [first["set_id"], second["set_id"], None]
    staff = actors[0]
    actors[0] = replace(staff, set_ids=frozenset({first["set_id"]}))
    _, scoped = await preview(client, RESOURCE, "update", source)
    assert scoped["items"][1]["errors"] == scoped["items"][2]["errors"]
    guidance = scoped["items"][2]["errors"][0]
    assert "use the Resource CSV import page" in guidance
    assert scoped["items"][1]["changes"] == {}
    await apply(client, RESOURCE, body, status=409)
    actors[0] = staff
    key = uuid4()
    assert (await apply(client, RESOURCE, body, key))["ready"] == 2
    async with database_engine.connect() as db:
        assert set(
            await db.scalars(select(activity.c.set_id).where(activity.c.correlation_id == key))
        ) == {first["set_id"], second["set_id"]}
    actors[0] = replace(staff, set_ids=frozenset({first["set_id"]}))
    await apply(client, RESOURCE, body, key, status=403)
    actors[0] = staff
    moved, _ = await preview(client, RESOURCE, "update", "ID,Lock Version,Title\neditor/test,2,C")
    async with database_engine.begin() as db:
        await db.execute(
            update(resources)
            .where(resources.c.id == "editor/test")
            .values(set_id=second["set_id"], lock_version=3)
        )
    await apply(client, RESOURCE, moved, status=409)
    _, mismatched = await preview(
        client,
        RESOURCE,
        "update",
        f"ID,Set ID,Lock Version,Title\neditor/test,{first['set_id']},3,X",
    )
    assert mismatched["ready"] == 0


async def test_assignment_from_resource_detail_reconciles_only_its_intake_row(api):
    client, actors, scope, _ = await seed(api)
    upload, _ = await preview(
        client, RESOURCE, "create", "ID,Title\nfirst,First draft\nsecond,Second draft"
    )
    imported = await apply(client, RESOURCE, upload)
    batch = RESOURCE + "/intake/" + imported["batch_id"]
    actors[0] = replace(actors[0], permissions=actors[0].permissions | {"resources:associate"})
    spec = dict(
        source_set_id=None,
        target_set_id=scope["set_id"],
        resource_version=1,
        reason="County collection",
        confirmed=True,
    )
    response = await client.put(BASE + "/first/set", json=spec, headers=headers())
    assert response.status_code == 200, response.text
    queue = (await client.get(batch)).json()
    assert queue["pending"] == 1 and [row["resource_id"] for row in queue["items"]] == ["second"]
    assert (await client.get(batch + "/receipt")).json() == imported


async def test_intake_save_edit_assign_and_replay(api, database_engine):
    client, actors, scope, _ = await seed(api)
    source = "ID,Title,Code\nnew-row,New draft,Legacy\neditor/test,Existing,\nother,Second,\nbad,,"
    unscoped, report = await preview(client, RESOURCE, "create", source)
    assert report["ready"] == 2
    assert [r["outcome"] for r in report["items"]] == ["create", "skipped", "create", "invalid"]
    upload_key = uuid4()
    saved = await apply(client, RESOURCE, unscoped, upload_key)
    assert saved == await apply(client, RESOURCE, unscoped, upload_key)
    assert saved["items"][0]["outcome"] == "created"
    listing = RESOURCE + "/intake"
    batch = listing + "/" + saved["batch_id"]
    assignment = batch + "/assignments"
    assert (await client.get(batch + "/receipt")).json() == saved
    assert (await client.get(listing)).json()[0]["pending"] == 2
    async with database_engine.connect() as db:
        assert await db.scalar(select(func.count()).select_from(resources)) == 3
    rows = (await client.get(batch + "?limit=1&offset=1")).json()
    assert [r["row_number"] for r in rows["items"]] == [3]
    detail_url = BASE + "/new-row"
    record = (await client.get(detail_url)).json()
    assert record["can_associate"] is False and record["editable"] is True
    assert record["id"] == "new-row" and record["set_id"] is None and record["source_id"] is None
    assert (await client.get(BASE, params={"q": "new-row"})).json()["total"] == 1
    assert "new-row" in (await client.get(RESOURCE + "/export")).text
    staff = actors[0]
    actors[0] = replace(staff, actor_id="colleague")
    assert (await client.get(detail_url)).status_code == 404
    assert (await client.get(BASE, params={"q": "new-row"})).json()["total"] == 0
    assert "new-row" not in (await client.get(RESOURCE + "/export")).text
    assert (await client.get(listing)).json() == []
    assert (await client.get(batch)).status_code == 404
    assert (await client.get(batch + "/receipt")).status_code == 404
    actors[0] = replace(actors[0], permissions=staff.permissions | {"resources:intake-manage"})
    assert (await client.get(batch)).json()["pending"] == 2
    selection = {"set_id": scope["set_id"], "rows": [1]}

    async def plan(body):
        response = await client.post(assignment + "/preview", headers=headers(), json=body)
        assert response.status_code == 200, response.text
        return {**body, "confirmed": True, "preview_hash": response.json()["preview_hash"]}

    body = await plan(selection)
    edit = {"lock_version": 1, "values": {"dct_title_s": "Revised draft"}}
    edited = await client.patch(detail_url, headers=headers(), json=edit)
    assert edited.status_code == 200, edited.text
    assert edited.json()["lock_version"] == 2
    assert (await client.post(assignment, headers=headers(), json=body)).status_code == 409
    body = await plan(selection)
    receipt_headers = headers()
    assigned = await client.post(assignment, headers=receipt_headers, json=body)
    assert assigned.status_code == 200, assigned.text
    assert assigned.json()["items"][0]["outcome"] == "assigned"
    assert (
        await client.post(assignment, headers=receipt_headers, json=body)
    ).json() == assigned.json()
    assert (await client.get(batch)).json()["pending"] == 1
    from app.resources.intake_models import batches
    from app.resources.models import evidence

    async with database_engine.connect() as db:
        assert (
            await db.scalar(select(resources.c.dct_title_s).where(resources.c.id == "new-row"))
            == "Revised draft"
        )
        assert await db.scalar(select(batches.c.original_csv)) == unscoped["csv"]
        record = await db.scalar(
            select(evidence.c.source_record).where(evidence.c.resource_id == "new-row")
        )
        assert "Legacy" in record["geomg_v1_source"].values()
    body = await plan({"set_id": scope["set_id"], "rows": None})
    applied = await client.post(assignment, headers=headers(), json=body)
    assert [r["outcome"] for r in applied.json()["items"]] == ["assigned"]
    assert [r["resource_id"] for r in (await client.get(batch)).json()["items"]] == []
    actors[0] = replace(actors[0], set_ids=frozenset())
    assert (
        await client.post(assignment, headers=receipt_headers, json=selection)
    ).status_code == 422
    assert (
        await client.post(assignment + "/preview", headers=headers(), json=selection)
    ).status_code == 404
    actors[0] = replace(staff, kind="service_account")
    assert (await client.get(listing)).status_code == 403


async def test_legacy_template_and_draft_defaults(api):
    client, _, scope, _ = await seed(api)
    source = document(
        [
            "ID",
            "Title",
            "Language",
            "B1G Language",
            "Publication State",
            "Code",
            "Date Accessioned",
            "Accrual Method",
        ],
        *[
            [f"sample-{i}", "Sample", "eng", "", "published", "Old", "2020-01-01", "Harvest"]
            for i in range(4)
        ],
    )
    body, report = await preview(client, RESOURCE, "create", source, set_id=scope["set_id"])
    assert report["ready"] == 4
    row = report["items"][0]
    assert row["changes"]["gbl_mdVersion_s"]["after"] == "Aardvark"
    assert "gbl_mdVersion_s" not in row["supplied_fields"]
    assert any("For publication" in w and "B1G Language" in w for w in row["warnings"])
    assert not any("Missing publication-schema" in w for w in row["warnings"])
    await apply(client, RESOURCE, body)
    saved = (await client.get(BASE + "/sample-0")).json()
    assert saved["metadata"]["gbl_mdVersion_s"] == "Aardvark"
    assert "gbl_mdVersion_s" not in saved["source_record"]
    assert saved["source_record"]["geomg_v1_source"]["Publication State"] == "published"
    crosswalk = (await client.get(RESOURCE + "/crosswalk")).text
    assert "b1g_publication_state_s" in crosswalk and "B1G Language,b1g_language_sm" in crosswalk


async def test_distribution_group_import_roundtrip_and_preview_binding(api, database_engine):
    client, _, _, _ = await seed(api)
    header = ",".join(COLUMNS)
    a = "editor/test,download,https://example.org/a,A"
    b = "editor/test,download,https://example.org/b,B"
    body, report = await preview(client, RESOURCE, "add_links", "\n".join([header, a, b]))
    assert report["items"][0]["input_rows"] == [1, 2]
    assert len(report["items"][0]["changes"]["distributions"]["after"]) == 3
    key = uuid4()
    result = await apply(client, RESOURCE, body, key)
    assert await apply(client, RESOURCE, body, key) == result
    async with database_engine.connect() as db:
        saved_links = dict(
            (await db.execute(select(distributions.c.url, distributions.c.id))).all()
        )
    exported = await client.get(RESOURCE + "/distributions/export")
    assert (await client.get(RESOURCE + "/distributions/template")).text.strip() == header
    assert (await preview(client, RESOURCE, "replace_links", exported.text))[1]["ready"] == 0
    _, conflict = await preview(
        client, RESOURCE, "add_links", "\n".join([header, a.replace(",A", ",New")])
    )
    assert any("Conflicting labels" in e for e in conflict["items"][0]["errors"])
    _, invalid = await preview(
        client,
        RESOURCE,
        "replace_links",
        "\n".join([header, b, "editor/test,unknown,https://example.org/c,C"]),
    )
    assert invalid["ready"] == 0 and "Row 2" in invalid["items"][0]["errors"][0]
    body, report = await preview(
        client, RESOURCE, "replace_links", "\n".join([header, b, a.replace(",A", ",New")])
    )
    assert report["items"][0]["link_changes"] == {
        "added": 0,
        "removed": 1,
        "relabeled": 1,
        "reordered": True,
    }
    change = report["items"][0]["changes"]["distributions"]
    assert [r["label"] for r in change["after"]] == ["B", "New"] and len(change["before"]) == 3
    async with database_engine.begin() as db:
        await db.execute(update(resources).values(lock_version=resources.c.lock_version + 1))
    await apply(client, RESOURCE, body, status=409)
    body, _ = await preview(client, RESOURCE, "replace_links", body["csv"])
    await apply(client, RESOURCE, body)
    async with database_engine.connect() as db:
        after = dict((await db.execute(select(distributions.c.url, distributions.c.id))).all())
        assert after == {
            url: link_id for url, link_id in saved_links.items() if not url.endswith("/original")
        }
        assert list(
            await db.scalars(select(distributions.c.label).order_by(distributions.c.position))
        ) == ["B", "New"]


async def test_intake_failed_assignment_rolls_back_and_rechecks_asserted_set(api, monkeypatch):
    from app.domain import DomainError
    from app.resources import intake

    client, _, scope, _ = await seed(api)
    source = f"ID,Title,Set ID\nnew,New,{scope['set_id']}\nwrong,Wrong,another-set"
    body, _ = await preview(client, RESOURCE, "create", source)
    saved = await apply(client, RESOURCE, body)
    batch = RESOURCE + "/intake/" + saved["batch_id"]
    url = batch + "/assignments"
    selection = {"set_id": scope["set_id"], "rows": None}
    plan = (await client.post(url + "/preview", json=selection, headers=headers())).json()
    assert [r["outcome"] for r in plan["items"]] == ["assign", "invalid"]
    confirm = {**selection, "confirmed": True, "preview_hash": plan["preview_hash"]}
    key = headers()

    async def fail(*args):
        raise DomainError(503, "unavailable", "Simulated audit failure")

    with monkeypatch.context() as patch:
        patch.setattr(intake, "log", fail)
        assert (await client.post(url, json=confirm, headers=key)).status_code == 503
    assert (await client.get(batch)).json()["pending"] == 2
    response = await client.post(url, json=confirm, headers=key)
    assert response.status_code == 200, response.text
    assert [r["outcome"] for r in response.json()["items"]] == ["assigned", "invalid"]
    assert (await client.get(batch)).json()["pending"] == 1


async def test_optional_set_migration_preserves_saved_pending_drafts(api, database_engine):
    from alembic import command
    from conftest import alembic_config
    from sqlalchemy import text

    from app.identity.actors import actor_identity

    client, actors = api
    batch_id = uuid4()
    async with database_engine.begin() as db:
        await db.run_sync(lambda sync: command.downgrade(alembic_config(sync), "intake_01"))
        actor_id = await actor_identity(db, actors[0])
        await db.execute(
            text("""INSERT INTO resource_intake_batches
            (id,actor_id,receipt_key,original_csv,headings) VALUES
            (:id,:actor,:key,'ID,Title','["ID","Title"]')"""),
            {"id": batch_id, "actor": actor_id, "key": uuid4()},
        )
        await db.execute(
            text("""INSERT INTO resource_intake_drafts
            (batch_id,row_number,resource_id,title,cells) VALUES
            (:id,1,'before-migration','Saved map','["before-migration","Saved map"]')"""),
            {"id": batch_id},
        )
        await db.run_sync(lambda sync: command.upgrade(alembic_config(sync), "head"))
    res = await client.get(BASE + "/before-migration")
    assert res.status_code == 200, res.text
    assert res.json()["set_id"] is None and res.json()["metadata"]["dct_title_s"] == "Saved map"
    page = (await client.get(RESOURCE + "/intake/" + str(batch_id))).json()
    assert page["items"][0]["catalog_id"] == "before-migration"


async def test_import_without_set_grants_and_update_before_assignment(api):
    client, actors = api
    staff = actors[0]
    actors[0] = replace(
        staff, permissions=frozenset({"resources:read", "resources:import"}), set_ids=frozenset()
    )
    body, plan = await preview(client, RESOURCE, "create", "ID,Title\nstandalone,Independent map")
    assert plan["ready"] == 1
    saved = await apply(client, RESOURCE, body)
    batch = RESOURCE + "/intake/" + saved["batch_id"]
    assert (await client.get(batch)).json()["items"][0]["catalog_id"] == "standalone"
    assert (await client.get(BASE + "/standalone/metadata")).json()[
        "dct_title_s"
    ] == "Independent map"
    assert (await client.get(BASE + "/standalone/relationships")).status_code == 200
    actors[0] = replace(
        staff, permissions=staff.permissions | {"resources:update"}, set_ids=frozenset()
    )
    body, plan = await preview(
        client, RESOURCE, "update", "ID,Lock Version,Title\nstandalone,1,Edited map"
    )
    assert plan["ready"] == 1
    assert (await apply(client, RESOURCE, body))["items"][0]["outcome"] == "updated"
    updated = (await client.get(BASE + "/standalone")).json()
    assert updated["set_id"] is None and updated["metadata"]["dct_title_s"] == "Edited map"


async def test_default_resource_import_creates_and_updates_by_id(api, database_engine):
    client, actors, scope, _ = await seed(api)
    source = "ID,Title\nnew-map,New map\neditor/test,Revised title"
    body, planned = await preview(client, RESOURCE, None, source)
    assert [r["outcome"] for r in planned["items"]] == ["create", "update"]
    assert [r["set_id"] for r in planned["items"]] == [None, scope["set_id"]]
    key = uuid4()
    saved = await apply(client, RESOURCE, body, key)
    assert saved == await apply(client, RESOURCE, body, key)
    assert [r["outcome"] for r in saved["items"]] == ["created", "updated"]
    batch = RESOURCE + "/intake/" + saved["batch_id"]
    assert (await client.get(batch)).json()["pending"] == 1
    assert (await client.get(batch + "/receipt")).json() == saved
    _, repeated = await preview(client, RESOURCE, None, source)
    assert [r["outcome"] for r in repeated["items"]] == ["unchanged", "unchanged"]

    changed, _ = await preview(client, RESOURCE, None, source.replace("New map", "Changed map"))
    async with database_engine.begin() as db:
        await db.execute(
            update(resources).where(resources.c.id == "new-map").values(lock_version=2)
        )
    await apply(client, RESOURCE, changed, status=409)
    _, stale = await preview(client, RESOURCE, None, "ID,Title,Lock Version\nnew-map,Changed map,1")
    assert stale["items"][0]["outcome"] == "conflict"

    actors[0] = replace(actors[0], set_ids=frozenset())
    await apply(client, RESOURCE, body, key, status=403)
    assert (await client.get(batch + "/receipt")).status_code == 403
    _, hidden = await preview(client, RESOURCE, None, source)
    assert hidden["items"][1]["outcome"] == "invalid"
    assert hidden["items"][1]["changes"] == {}


async def test_default_resource_import_respects_create_and_update_grants(api):
    client, actors = api
    staff = actors[0]
    actors[0] = replace(
        staff, permissions=frozenset({"resources:read", "resources:import"}), set_ids=frozenset()
    )
    source = "ID,Title\nsolo,First draft"
    body, _ = await preview(client, RESOURCE, None, source)
    await apply(client, RESOURCE, body)
    mixed = "ID,Title\nsolo,Edited\nsecond,Second draft"
    _, protected = await preview(client, RESOURCE, None, mixed)
    assert [r["outcome"] for r in protected["items"]] == ["invalid", "create"]
    actors[0] = replace(actors[0], permissions=actors[0].permissions | {"resources:update"})
    body, planned = await preview(client, RESOURCE, None, mixed)
    assert [r["outcome"] for r in planned["items"]] == ["update", "create"]
    race, _ = await preview(client, RESOURCE, None, "ID,Title\nsecond,Different")
    await apply(client, RESOURCE, race)
    await apply(client, RESOURCE, body, status=409)
    assert (await client.get(BASE + "/solo")).json()["metadata"]["dct_title_s"] == "First draft"


async def test_default_scoped_import_can_replay_partial_success(api):
    client, _, scope, _ = await seed(api)
    source = "ID,Title\nnew-map,New map\neditor/test,Edited\nbad,"
    body, planned = await preview(client, RESOURCE, None, source, set_id=scope["set_id"])
    assert [r["outcome"] for r in planned["items"]] == ["create", "update", "invalid"]
    key = uuid4()
    saved = await apply(client, RESOURCE, body, key)
    assert saved["batch_id"] is None
    assert [r["outcome"] for r in saved["items"]] == ["created", "updated", "invalid"]
    assert saved == await apply(client, RESOURCE, body, key)
    assert (await client.get(BASE + "/new-map")).json()["set_id"] == scope["set_id"]


async def test_blank_cells_clear_existing_fields_and_omit_new_values(api):
    client, _, scope, _ = await seed(api)
    source = (
        "ID,Title,Provider,Description,Distributions,Set ID,Source ID\n"
        "editor/test,Original title,,,,,\n"
        "new-map,New map,,,,,"
    )
    body, planned = await preview(client, RESOURCE, None, source)
    existing, new = planned["items"]
    assert existing["outcome"] == "update"
    assert set(existing["clear_fields"]) == {
        "schema_provider_s",
        "dct_description_sm",
        "distributions",
    }
    assert existing["changes"]["schema_provider_s"] == {"before": "Provider", "after": None}
    assert existing["changes"]["dct_description_sm"] == {"before": ["One", "Two"], "after": None}
    assert existing["changes"]["distributions"]["before"]
    assert existing["changes"]["distributions"]["after"] == []
    assert new["outcome"] == "create" and not new["clear_fields"]
    assert new["set_id"] is None

    saved = await apply(client, RESOURCE, body)
    assert [r["outcome"] for r in saved["items"]] == ["updated", "created"]
    exported = list(csv.DictReader(io.StringIO((await client.get(RESOURCE + "/export")).text)))
    record = next(r for r in exported if r["id"] == "editor/test")
    assert record["set_id"] == scope["set_id"]
    assert record["schema_provider_s"] == record["dct_description_sm"] == ""
    assert record["distributions"] == "[]"
    assert record["gbl_indexYear_im"] == "[1900]"
    assert all("__clear" not in column for column in record)
    _, repeated = await preview(client, RESOURCE, None, source)
    assert [r["outcome"] for r in repeated["items"]] == ["unchanged", "unchanged"]

    _, invalid = await preview(client, RESOURCE, None, "ID,Title\neditor/test,")
    assert invalid["items"][0]["errors"] == ["Title cannot be cleared"]
