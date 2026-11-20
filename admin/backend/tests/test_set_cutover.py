"""Populated cutover preserves legacy facts and requires reviewed Set identities."""

import argparse
import json
from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4

import pytest
from alembic import command
from conftest import alembic_config
from legacy_data import lifecycle
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.sets import cutover

pytestmark = pytest.mark.integration


async def seed(engine):
    async with engine.begin() as conn:
        await conn.run_sync(lambda sync: command.downgrade(alembic_config(sync), "0018"))
        scope = await lifecycle(conn)
        actor = await conn.scalar(text("SELECT created_by_actor_id FROM lifecycles"))
        await conn.execute(
            text("""INSERT INTO sources
            (source_id, title, created_by_actor_id, updated_by_actor_id)
            VALUES ('parent', 'Original archive', :actor, :actor)"""),
            {"actor": actor},
        )
        await conn.execute(
            text("""INSERT INTO sets
            (set_id, source_id, title, created_by_actor_id, updated_by_actor_id)
            VALUES ('existing-set', 'parent', 'Existing maps', :actor, :actor)"""),
            {"actor": actor},
        )
        receipt = uuid4()
        await conn.execute(
            text("""INSERT INTO resource_imports
            (id, actor_id, lifecycle_id, request_hash, response)
            VALUES (:id, :actor, :scope, :hash, CAST(:response AS jsonb))"""),
            {
                "id": receipt,
                "actor": actor,
                "scope": scope,
                "hash": "0" * 64,
                "response": json.dumps({"lifecycle_id": str(scope), "created": 3, "legacy": True}),
            },
        )
        await conn.execute(
            text("""INSERT INTO resources
            (id, dct_title_s, lifecycle_id, source_id, publication_state,
             created_by_actor_id, import_id)
            VALUES (:id, :title, :scope, :source, 'draft', :actor, :receipt)"""),
            [
                {
                    "id": rid,
                    "title": "Preserved " + rid,
                    "scope": scope,
                    "source": source,
                    "actor": actor,
                    "receipt": str(receipt),
                }
                for rid, source in [("first", "parent"), ("second", "parent"), ("unmapped", None)]
            ],
        )
        await conn.execute(
            text("""INSERT INTO resource_import_evidence
            (resource_id, import_id, source_record, warnings)
            VALUES (:id, :receipt, CAST(:record AS jsonb), '{}')"""),
            [
                {"id": rid, "receipt": receipt, "record": json.dumps({"id": rid, "original": True})}
                for rid in ["first", "second", "unmapped"]
            ],
        )
        await conn.execute(
            text("""INSERT INTO resource_selections
            (selection_id, actor_id, idempotency_key, request_hash, query, sealed)
            VALUES (:id, :actor, :key, :hash, CAST(:query AS jsonb), true)"""),
            {
                "id": uuid4(),
                "actor": actor,
                "key": uuid4(),
                "hash": "f" * 64,
                "query": json.dumps({"lifecycle_id": str(scope), "q": "empty legacy result"}),
            },
        )
    return {
        "schema_version": 1,
        "new_sources": [{"source_id": "recovered", "title": "Reviewed origin"}],
        "new_sets": [
            {
                "set_id": "sibling",
                "source_id": "parent",
                "title": "Another collection",
                "status": "active",
            },
            {
                "set_id": "recovered-set",
                "source_id": "recovered",
                "title": "Recovered maps",
                "status": "active",
                "represented_by_id": "unmapped",
            },
        ],
        "assignments": [
            {
                "lifecycle_id": str(scope),
                "source_id": "parent",
                "target_set_id": target,
                "resource_ids": [rid],
                "reason": "Reviewed distinct collection",
            }
            for rid, target in [("first", "existing-set"), ("second", "sibling")]
        ]
        + [
            {
                "lifecycle_id": str(scope),
                "source_id": None,
                "target_set_id": "recovered-set",
                "reason": "Reviewed metadata",
                "source_reconciliation": "Verified publisher and endpoint",
            }
        ],
    }


async def reviewed(engine, document):
    manifest = cutover.Manifest.model_validate(document)
    async with engine.begin() as conn:
        await conn.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
        result = await conn.run_sync(lambda sync: cutover.preview(sync, manifest))
    return manifest, result


async def apply(engine, manifest, preview_hash):
    async with engine.begin() as conn:

        def migrate(sync):
            config = alembic_config(sync)
            config.attributes["set_cutover"] = {
                "manifest": manifest.model_dump(mode="json"),
                "preview_hash": preview_hash,
                "reviewed_by": "Test maintainer",
                "reason": "Reviewed migration rehearsal",
            }
            command.upgrade(config, "head")

        await conn.run_sync(migrate)


async def history(conn):
    return {
        table: (await conn.execute(text(f"SELECT to_jsonb(t) FROM {table} t ORDER BY {key}")))
        .scalars()
        .all()
        for table, key in [
            ("resource_imports", "id"),
            ("resource_import_evidence", "resource_id"),
            ("lifecycles", "lifecycle_id"),
            ("resource_selections", "selection_id"),
        ]
    }


async def test_cutover_preserves_multi_set_receipts_and_immutable_mapping(database_engine):
    manifest, plan = await reviewed(database_engine, await seed(database_engine))
    assert plan["ready"] and plan["resource_count"] == 3 and plan["preserved_imports"] == 1
    async with database_engine.connect() as conn:
        before = await history(conn)
        old_events = (
            (await conn.execute(text("SELECT to_jsonb(t) FROM lifecycle_activity_entries t")))
            .scalars()
            .all()
        )
    await apply(database_engine, manifest, plan["preview_hash"])
    async with database_engine.connect() as conn:
        after = await history(conn)
        assert after["resource_imports"] == [
            {**row, "set_id": None, "intake_batch_id": None} for row in before["resource_imports"]
        ]
        assert after["resource_import_evidence"] == before["resource_import_evidence"]
        assert after["lifecycles"] == before["lifecycles"]
        assert after["resource_selections"] == before["resource_selections"]
        assert (
            await conn.execute(
                text("""SELECT to_jsonb(t) FROM lifecycle_activity_entries t
            WHERE lifecycle_id IS NOT NULL""")
            )
        ).scalars().all() == old_events
        rows = (
            (
                await conn.execute(
                    text("""SELECT r.id, r.set_id, r.legacy_source_id, r.lock_version,
            r.dct_title_s, s.source_id FROM resources r JOIN sets s USING(set_id) ORDER BY r.id""")
                )
            )
            .mappings()
            .all()
        )
        assert [(r["id"], r["set_id"], r["source_id"]) for r in rows] == [
            ("first", "existing-set", "parent"),
            ("second", "sibling", "parent"),
            ("unmapped", "recovered-set", "recovered"),
        ]
        assert all(
            r["lock_version"] == 2 and r["dct_title_s"] == "Preserved " + r["id"] for r in rows
        )
        assert (
            await conn.scalar(
                text("SELECT count(*) FROM resource_set_cutovers WHERE resource_version = 1")
            )
            == 3
        )
        assert (
            await conn.scalar(
                text(
                    "SELECT count(*) FROM lifecycle_activity_entries WHERE action = 'set.migrated'"
                )
            )
            == 3
        )
        receipt = await conn.run_sync(
            lambda sync: cutover.applied_receipt(sync, manifest, plan["preview_hash"])
        )
        assert receipt["already_applied"] and receipt["resource_count"] == 3
    for sql in [
        "UPDATE resource_set_cutovers SET reason = 'changed'",
        "DELETE FROM set_ownership_cutovers",
    ]:
        with pytest.raises(DBAPIError, match="immutable"):
            async with database_engine.begin() as conn:
                await conn.execute(text(sql))
    with pytest.raises(DBAPIError, match="Cannot discard native Set ownership"):
        async with database_engine.begin() as conn:
            await conn.run_sync(lambda sync: command.downgrade(alembic_config(sync), "0021"))


@pytest.mark.parametrize(
    "change,message",
    [
        (lambda p: p["assignments"].pop(), "exactly one"),
        (lambda p: p["assignments"].append(deepcopy(p["assignments"][0])), "exactly one"),
        (lambda p: p["assignments"][0].update(resource_ids=["missing"]), "missing Resources"),
        (
            lambda p: p["assignments"][0].update(target_set_id="missing"),
            "unknown Lifecycle or target Set",
        ),
        (lambda p: p["assignments"][2].pop("source_reconciliation"), "Source change"),
        (lambda p: p["new_sets"][0].update(status="inactive"), "preserve active"),
        (
            lambda p: p["new_sets"].append(deepcopy(p["new_sets"][0])),
            "Duplicate or existing new Set",
        ),
        (
            lambda p: p["new_sources"].append({"source_id": "parent", "title": "Overwrite"}),
            "Duplicate or existing new Source",
        ),
        (lambda p: p["new_sets"][0].update(source_id="absent"), "Source does not exist"),
        (lambda p: p["new_sets"][0].update(represented_by_id="absent"), "representative Resource"),
        (lambda p: p["new_sets"][0].update(workflow_catalog_id="absent"), "workflow catalog"),
    ],
)
async def test_invalid_mapping_cannot_mutate(database_engine, change, message):
    document = await seed(database_engine)
    change(document)
    manifest, plan = await reviewed(database_engine, document)
    assert not plan["ready"] and message in "; ".join(plan["errors"])
    with pytest.raises(ValueError, match="Cutover is not ready"):
        await apply(database_engine, manifest, plan["preview_hash"])
    async with database_engine.connect() as conn:
        assert await conn.scalar(text("SELECT version_num FROM alembic_version")) == "0018"
        assert await conn.scalar(text("SELECT count(*) FROM sources")) == 1
        assert await conn.scalar(text("SELECT count(*) FROM resources WHERE lock_version = 1")) == 3


async def test_stale_data_and_manifest_require_fresh_review(database_engine):
    document = await seed(database_engine)
    manifest, plan = await reviewed(database_engine, document)
    async with database_engine.begin() as conn:
        await conn.execute(text("UPDATE resources SET lock_version = 2 WHERE id = 'first'"))
    with pytest.raises(ValueError, match="preview changed"):
        await apply(database_engine, manifest, plan["preview_hash"])
    _, current = await reviewed(database_engine, document)
    altered = deepcopy(document)
    altered["new_sets"][0]["title"] = "Changed proposal"
    with pytest.raises(ValueError, match="preview changed"):
        await apply(
            database_engine, cutover.Manifest.model_validate(altered), current["preview_hash"]
        )


async def test_failure_rolls_back_schema_data_and_receipt_then_retries(database_engine):
    manifest, plan = await reviewed(database_engine, await seed(database_engine))
    async with database_engine.begin() as conn:
        await conn.execute(
            text("""CREATE FUNCTION reject_cutover() RETURNS trigger
            LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'synthetic failure'; END $$""")
        )
        await conn.execute(
            text("""CREATE TRIGGER reject_cutover BEFORE INSERT ON lifecycle_activity_entries
            FOR EACH ROW EXECUTE FUNCTION reject_cutover()""")
        )
    with pytest.raises(DBAPIError, match="synthetic failure"):
        await apply(database_engine, manifest, plan["preview_hash"])
    async with database_engine.begin() as conn:
        assert await conn.scalar(text("SELECT version_num FROM alembic_version")) == "0018"
        assert await conn.scalar(text("SELECT to_regclass('set_ownership_cutovers')")) is None
        assert await conn.scalar(text("SELECT count(*) FROM sets")) == 1
        await conn.execute(text("DROP TRIGGER reject_cutover ON lifecycle_activity_entries"))
    await apply(database_engine, manifest, plan["preview_hash"])


async def test_empty_scope_disposition_and_existing_grants_are_not_inferred(database_engine):
    document = await seed(database_engine)
    async with database_engine.begin() as conn:
        empty = await lifecycle(conn)
    _, plan = await reviewed(database_engine, document)
    assert not plan["ready"] and "Empty Lifecycles" in "; ".join(plan["errors"])
    document["archive_empty_lifecycles"] = [str(empty)]
    _, plan = await reviewed(database_engine, document)
    assert plan["ready"]
    async with database_engine.begin() as conn:
        await conn.execute(
            text("INSERT INTO identity_accounts(actor_id) SELECT id FROM actors LIMIT 1")
        )
    _, plan = await reviewed(database_engine, document)
    assert not plan["ready"] and "identity_accounts" in "; ".join(plan["errors"])


async def test_cli_inventory_preview_apply_and_lost_response_replay(
    database_engine, tmp_path, monkeypatch
):
    document = await seed(database_engine)
    monkeypatch.setattr(
        cutover, "get_settings", lambda: SimpleNamespace(app_env="test", database_url="isolated")
    )
    monkeypatch.setattr(cutover, "create_async_engine", lambda _: database_engine)
    output = tmp_path / "report.json"
    args = argparse.Namespace(operation="inventory", output=output)
    assert await cutover.run(args) == 0
    inventory = json.loads(output.read_text())
    assert inventory["resource_count"] == 3
    assert all(r["target_set_id"] is None for r in inventory["draft_manifest"]["assignments"])
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(document))
    args = argparse.Namespace(operation="preview", output=output, manifest=path)
    assert await cutover.run(args) == 0
    plan = json.loads(output.read_text())
    args = argparse.Namespace(
        operation="apply",
        output=output,
        manifest=path,
        preview_hash=plan["preview_hash"],
        reviewed_by="Test steward",
        reason="Reviewed",
    )
    assert await cutover.run(args) == 0
    assert await cutover.run(args) == 0
    assert json.loads(output.read_text())["already_applied"]
    args.preview_hash = "0" * 64
    with pytest.raises(ValueError, match="was not applied"):
        await cutover.run(args)
    monkeypatch.setattr(cutover, "get_settings", lambda: SimpleNamespace(app_env="production"))
    with pytest.raises(ValueError, match="Production cutover"):
        await cutover.run(args)


def test_manifest_rejects_unpinned_ids_duplicates_and_extra_fields():
    with pytest.raises(ValidationError):
        cutover.NewSource(title="Generated identity would be unstable")
    with pytest.raises(ValidationError):
        cutover.Assignment(
            lifecycle_id=uuid4(),
            source_id=None,
            target_set_id="target",
            resource_ids=["duplicate", "duplicate"],
            reason="Reviewed",
        )
    with pytest.raises(ValidationError):
        cutover.Manifest.model_validate({"schema_version": 1, "guess_sources": True})


async def test_large_catalog_hash_and_assignment_cover_all_keyset_batches(database_engine):
    document = await seed(database_engine)
    scope = document["assignments"][0]["lifecycle_id"]
    async with database_engine.begin() as conn:
        await conn.execute(
            text("""INSERT INTO resources
            (id, dct_title_s, lifecycle_id, source_id, publication_state, created_by_actor_id)
            SELECT 'bulk-' || lpad(n::text, 5, '0'), 'Bulk map', l.lifecycle_id,
                   'parent', 'draft', l.created_by_actor_id
            FROM generate_series(1, 2001) n CROSS JOIN lifecycles l""")
        )
        await conn.execute(
            text("""INSERT INTO resource_imports
            (id, actor_id, lifecycle_id, request_hash, response)
            SELECT gen_random_uuid(), l.created_by_actor_id, l.lifecycle_id,
                   repeat('1', 64), jsonb_build_object('original', n)
            FROM generate_series(1, 101) n CROSS JOIN lifecycles l""")
        )
    document["assignments"].append(
        {
            "lifecycle_id": scope,
            "source_id": "parent",
            "target_set_id": "existing-set",
            "resource_ids": [f"bulk-{n:05}" for n in range(1, 2002)],
            "reason": "Reviewed subset",
        }
    )
    manifest, plan = await reviewed(database_engine, document)
    assert plan["ready"] and plan["resource_count"] == 2004 and plan["preserved_imports"] == 102
    async with database_engine.begin() as conn:
        await conn.execute(text("UPDATE resources SET lock_version = 2 WHERE id = 'unmapped'"))
    with pytest.raises(ValueError, match="preview changed"):
        await apply(database_engine, manifest, plan["preview_hash"])
    manifest, plan = await reviewed(database_engine, document)
    await apply(database_engine, manifest, plan["preview_hash"])
    async with database_engine.connect() as conn:
        assert await conn.scalar(text("SELECT count(*) FROM resource_set_cutovers")) == 2004
        assert (
            await conn.scalar(text("SELECT count(*) FROM resource_imports WHERE set_id IS NULL"))
            == 102
        )


@pytest.mark.parametrize(
    "legacy_status,target_status", [("paused", "inactive"), ("retired", "retired")]
)
async def test_cutover_preserves_inactive_and_retired_scope_without_scheduling(
    database_engine, legacy_status, target_status
):
    document = await seed(database_engine)
    async with database_engine.begin() as conn:
        await conn.run_sync(lambda sync: command.upgrade(alembic_config(sync), "0021"))
        await conn.execute(
            text("UPDATE lifecycles SET status = :status, review_interval = '3 months'"),
            {"status": legacy_status},
        )
        await conn.execute(text("UPDATE sets SET status = :status"), {"status": target_status})
    for row in document["new_sets"]:
        row["status"] = target_status
        row["review_interval"] = "P3M"
    manifest, plan = await reviewed(database_engine, document)
    assert plan["ready"]
    await apply(database_engine, manifest, plan["preview_hash"])
    async with database_engine.connect() as conn:
        assert (await conn.execute(text("SELECT DISTINCT status FROM sets"))).scalars().all() == [
            target_status
        ]
        assert await conn.scalar(text("SELECT count(*) FROM work_tasks")) == 0
        assert await conn.scalar(text("SELECT count(*) FROM set_maintenance")) == 0
        assert (
            await conn.scalar(
                text("SELECT count(*) FROM resources WHERE publication_state = 'draft'")
            )
            == 3
        )


@pytest.mark.parametrize(
    "existing",
    [
        "workflows",
        "jobs",
        "resource_selection_items",
        "identity_invitations",
        "unsealed_selections",
    ],
)
async def test_other_operational_scopes_remain_guarded(database_engine, existing):
    document = await seed(database_engine)
    async with database_engine.begin() as conn:
        actor = await conn.scalar(text("SELECT created_by_actor_id FROM lifecycles"))
        scope = await conn.scalar(text("SELECT lifecycle_id FROM lifecycles"))
        params = {"actor": actor, "scope": scope, "id": uuid4(), "hash": "2" * 64}
        if existing == "workflows":
            statement = """INSERT INTO workflows(workflow_id, lifecycle_id, title,
                created_by_actor_id, updated_by_actor_id)
                VALUES (:id, :scope, 'Existing workflow', :actor, :actor)"""
        elif existing == "jobs":
            statement = """INSERT INTO jobs(job_id, lifecycle_id, actor_id, operation,
                idempotency_key, request_hash, software_version)
                VALUES (:id, :scope, :actor, 'resources.validate', :id, :hash, 'legacy')"""
        elif existing == "identity_invitations":
            statement = """INSERT INTO identity_invitations(invitation_id, token_hash,
                idp_entity_id, permissions,
                lifecycle_ids, all_lifecycles, created_by_actor_id, expires_at)
                VALUES (:id, :hash, 'https://idp.example.org', '{}', '{}', false,
                        :actor, now() + interval '1 day')"""
        else:
            statement = """INSERT INTO resource_selections(selection_id, actor_id, idempotency_key,
                request_hash, query)
                VALUES (:id, :actor, :id, :hash, '{}')"""
        await conn.execute(text(statement), params)
        if existing == "resource_selection_items":
            await conn.execute(
                text("""INSERT INTO resource_selection_items
                (selection_id, resource_id, lifecycle_id, resource_version)
                VALUES (:id, 'first', :scope, 1)"""),
                params,
            )
            await conn.execute(
                text("UPDATE resource_selections SET sealed = true WHERE selection_id = :id"),
                params,
            )
    manifest, plan = await reviewed(database_engine, document)
    assert not plan["ready"] and existing in "; ".join(plan["errors"])
    with pytest.raises(ValueError, match="Cutover is not ready"):
        await apply(database_engine, manifest, plan["preview_hash"])
