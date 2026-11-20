"""Reviewed local migration from legacy Resource ownership to managing Sets.

Preview is read-only. Apply is an explicit Alembic operation, never an application
API or an automatic startup migration. Original receipts and evidence stay intact.
"""

import argparse
import asyncio
import hashlib
import json
from pathlib import Path
from typing import Literal
from uuid import NAMESPACE_URL, UUID, uuid5

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import get_settings
from app.sets.schemas import SetFields, SetID, SetStatus
from app.sources.schemas import SourceCreate, SourceID

UNSUPPORTED = (
    "workflows",
    "jobs",
    "resource_selection_items",
    "identity_accounts",
    "identity_invitations",
)
SNAPSHOT_TABLES = (
    ("lifecycles", "lifecycle_id"),
    ("sources", "source_id"),
    ("sets", "set_id"),
    ("resource_imports", "id"),
    ("resource_selections", "selection_id"),
)
MAPPING = """WITH mapping AS (
    SELECT * FROM jsonb_to_recordset(CAST(:mapping AS jsonb)) AS m(
        mapping_id integer, lifecycle_id uuid, source_id text, target_set_id text,
        resource_ids text[], reason text, source_reconciliation text)
), matched AS (
    SELECT r.id, r.lock_version, r.updated_at AS original_updated_at, m.*
    FROM resources r JOIN mapping m
    ON r.lifecycle_id = m.lifecycle_id AND r.source_id IS NOT DISTINCT FROM m.source_id
    AND (m.resource_ids IS NULL OR r.id = ANY(m.resource_ids))
) """


class Definition(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class NewSource(SourceCreate):
    source_id: SourceID = Field(...)


class NewSet(SetFields):
    set_id: SetID
    source_id: SourceID
    status: SetStatus
    represented_by_id: str | None = Field(default=None, min_length=1, max_length=512)


class Assignment(Definition):
    lifecycle_id: UUID
    source_id: SourceID | None
    target_set_id: SetID
    resource_ids: list[str] | None = Field(default=None, min_length=1)
    reason: str = Field(min_length=1, max_length=1000)
    source_reconciliation: str | None = Field(default=None, min_length=1, max_length=1000)

    @field_validator("resource_ids")
    @classmethod
    def explicit_ids(cls, value):
        if value is not None and (
            len(value) != len(set(value))
            or any(
                not rid.strip() or len(rid) > 512 or any(ord(c) < 32 for c in rid) for rid in value
            )
        ):
            raise ValueError("Resource IDs must be unique, nonblank and at most 512 characters")
        return value


class Manifest(Definition):
    schema_version: Literal[1]
    new_sources: list[NewSource] = []
    new_sets: list[NewSet] = []
    assignments: list[Assignment] = []
    archive_empty_lifecycles: list[UUID] = []


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value):
    return hashlib.sha256(encoded(value).encode()).hexdigest()


def mappings(manifest):
    return encoded(
        [
            {"mapping_id": index, **row.model_dump(mode="json")}
            for index, row in enumerate(manifest.assignments)
        ]
    )


def snapshot(connection):
    """Bound memory while pinning every Resource version and catalog definition."""
    revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
    if revision not in {"0018", "0019", "0020", "0021"}:
        raise ValueError("Cutover preview requires legacy revision 0018 through 0021")
    result = {"source_revision": revision}
    fingerprint = hashlib.sha256()
    for table, key in SNAPSHOT_TABLES:
        values, after, count = [], None, 0
        while True:
            # Fixed identifiers only. Hash large immutable receipts in PostgreSQL;
            # do not fetch their potentially large CSV result documents into Python.
            projection = (
                "encode(sha256(convert_to(to_jsonb(t)::text, 'UTF8')), 'hex')"
                if table in {"resource_imports", "resource_selections"}
                else "to_jsonb(t)::text"
            )
            condition = f"WHERE {key} > :after" if after is not None else ""
            rows = connection.execute(
                text(
                    f"SELECT {key}, {projection} FROM {table} t {condition} "
                    f"ORDER BY {key} LIMIT 100"
                ),
                {"after": after},
            ).all()
            if not rows:
                break
            for _identifier, raw in rows:
                value = (
                    raw if table in {"resource_imports", "resource_selections"} else json.loads(raw)
                )
                fingerprint.update(encoded([table, value]).encode() + b"\n")
                count += 1
                if table not in {"resource_imports", "resource_selections"}:
                    values.append(value)
            after = rows[-1][0]
        if table in {"resource_imports", "resource_selections"}:
            result["import_count" if table == "resource_imports" else "selection_count"] = count
        else:
            result[table] = values
    # Large Resource catalogs stream into a digest; no browser or report gets every row.
    count, after = 0, None
    while True:
        # Keyset batches avoid a long-lived PostgreSQL portal: asyncpg portals
        # can hold a table in use even after Result.close(), preventing the DDL
        # that follows the locked preview in this same atomic transaction.
        condition = "WHERE id > :after" if after is not None else ""
        statement = text(f"""SELECT id, jsonb_build_array(id, lifecycle_id, source_id,
            lock_version, publication_state, b1g_code_s)::text FROM resources
            {condition} ORDER BY id LIMIT 1000""")
        rows = connection.execute(statement, {"after": after}).all()
        if not rows:
            break
        for _identifier, raw in rows:
            fingerprint.update(raw.encode() + b"\n")
            count += 1
        after = rows[-1][0]
    result["resource_count"] = count
    result["unsupported"] = {
        table: connection.scalar(text(f"SELECT count(*) FROM {table}")) for table in UNSUPPORTED
    }
    result["unsupported"]["unsealed_selections"] = connection.scalar(
        text("SELECT count(*) FROM resource_selections WHERE NOT sealed")
    )
    fingerprint.update(encoded(result["unsupported"]).encode())
    result["snapshot_hash"] = fingerprint.hexdigest()
    result["groups"] = [
        dict(row)
        for row in connection.execute(
            text("""
        SELECT lifecycle_id::text, source_id, count(*) AS resource_count
        FROM resources GROUP BY lifecycle_id, source_id ORDER BY lifecycle_id, source_id
    """)
        ).mappings()
    ]
    return result


def preview(connection, manifest):
    inventory = snapshot(connection)
    errors = []
    for table, count in inventory["unsupported"].items():
        if count:
            errors.append(
                f"{table}: {count} existing records require separate scope reconciliation"
            )
    sources = {row["source_id"]: row for row in inventory["sources"]}
    targets = {row["set_id"]: row for row in inventory["sets"]}
    lifecycles = {row["lifecycle_id"]: row for row in inventory["lifecycles"]}
    for row in manifest.new_sources:
        if row.source_id in sources:
            errors.append(f"Duplicate or existing new Source: {row.source_id}")
        sources[row.source_id] = row.model_dump(mode="json")
    for row in manifest.new_sets:
        if row.set_id in targets:
            errors.append(f"Duplicate or existing new Set: {row.set_id}")
        if row.source_id not in sources:
            errors.append(f"New Set {row.set_id}: Source does not exist")
        if row.workflow_catalog_id is not None and not connection.scalar(
            text("SELECT 1 FROM workflow_catalog WHERE workflow_id = :id"),
            {"id": row.workflow_catalog_id},
        ):
            errors.append(f"New Set {row.set_id}: workflow catalog definition does not exist")
        if row.represented_by_id is not None and not connection.scalar(
            text("SELECT 1 FROM resources WHERE id = :id"), {"id": row.represented_by_id}
        ):
            errors.append(f"New Set {row.set_id}: representative Resource does not exist")
        targets[row.set_id] = row.model_dump(mode="json")
    for index, row in enumerate(manifest.assignments):
        legacy, target = lifecycles.get(str(row.lifecycle_id)), targets.get(row.target_set_id)
        if legacy is None or target is None:
            errors.append(f"Assignment {index}: unknown Lifecycle or target Set")
            continue
        expected_status = {"paused": "inactive"}.get(legacy["status"], legacy["status"])
        if target["status"] != expected_status:
            errors.append(f"Assignment {index}: target Set must preserve {expected_status} state")
        if row.source_id != target["source_id"] and not row.source_reconciliation:
            errors.append(f"Assignment {index}: Source change requires explicit reconciliation")
    params = {"mapping": mappings(manifest)}
    counts = dict(
        connection.execute(
            text(
                MAPPING
                + """
        SELECT mapping_id, count(*) FROM matched GROUP BY mapping_id
    """
            ),
            params,
        ).all()
    )
    for index, row in enumerate(manifest.assignments):
        count = counts.get(index, 0)
        if not count or (row.resource_ids is not None and count != len(row.resource_ids)):
            errors.append(f"Assignment {index}: missing Resources or mismatched legacy ownership")
    invalid = (
        connection.execute(
            text(
                MAPPING
                + """
        SELECT r.id, count(m.mapping_id) AS assignments, count(*) OVER () AS total
        FROM resources r LEFT JOIN matched m ON m.id = r.id
        GROUP BY r.id HAVING count(m.mapping_id) <> 1 ORDER BY r.id LIMIT 25
    """
            ),
            params,
        )
        .mappings()
        .all()
    )
    if invalid:
        errors.append(f"{invalid[0]['total']} Resources must have exactly one explicit assignment")
    occupied = {row["lifecycle_id"] for row in inventory["groups"]}
    archived = {str(value) for value in manifest.archive_empty_lifecycles}
    if archived - (lifecycles.keys() - occupied):
        errors.append("Only existing empty Lifecycles may be archived without a Set mapping")
    if lifecycles.keys() - occupied - archived:
        errors.append("Empty Lifecycles need an explicit archive disposition")
    used = {row.target_set_id for row in manifest.assignments}
    if any(row.set_id not in used for row in manifest.new_sets):
        errors.append("Every new Set must have explicitly assigned Resources")
    used_sources = {row.source_id for row in manifest.new_sets}
    if any(row.source_id not in used_sources for row in manifest.new_sources):
        errors.append("Every new Source must own an explicitly defined new Set")
    return {
        "preview_hash": digest(
            {"manifest": manifest.model_dump(mode="json"), "snapshot": inventory["snapshot_hash"]}
        ),
        "manifest_hash": digest(manifest.model_dump(mode="json")),
        "snapshot_hash": inventory["snapshot_hash"],
        "resource_count": inventory["resource_count"],
        "preserved_imports": inventory["import_count"],
        "preserved_selections": inventory["selection_count"],
        "assignments": [
            {"mapping_id": i, "resource_count": counts.get(i, 0), **row.model_dump(mode="json")}
            for i, row in enumerate(manifest.assignments)
        ],
        "invalid_resources": [dict(row) for row in invalid],
        "errors": errors,
        "ready": not errors,
    }


def draft(inventory):
    """No target IDs, identities or grouping policies are inferred."""
    return {
        "schema_version": 1,
        "new_sources": [],
        "new_sets": [],
        "assignments": [
            {
                "lifecycle_id": row["lifecycle_id"],
                "source_id": row["source_id"],
                "target_set_id": None,
                "reason": None,
                "source_reconciliation": None,
                "resource_ids": None,
            }
            for row in inventory["groups"]
        ],
        "archive_empty_lifecycles": [],
    }


class Approval(Definition):
    manifest: Manifest
    preview_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    reviewed_by: str = Field(min_length=1, max_length=250)
    reason: str = Field(min_length=1, max_length=1000)


def prepare_migration(connection, approval):
    approval = Approval.model_validate(approval)
    # Populated cutover is an offline maintainer operation. Locks also prevent a
    # stale preview from racing an accidentally still-running application writer.
    connection.execute(text("SELECT pg_advisory_xact_lock(718443802)"))
    connection.execute(
        text("""LOCK TABLE actors, sources, lifecycles, sets, resources,
        resource_imports, workflows, jobs, resource_selections, resource_selection_items,
        identity_accounts, identity_invitations IN ACCESS EXCLUSIVE MODE""")
    )
    result = preview(connection, approval.manifest)
    if result["errors"]:
        raise ValueError("Cutover is not ready: " + "; ".join(result["errors"]))
    if result["preview_hash"] != approval.preview_hash:
        raise ValueError("Cutover preview changed; review the current data and manifest again")
    return approval, result


def create_audit_tables(connection):
    connection.execute(
        text("""CREATE TABLE set_ownership_cutovers (
        cutover_id uuid PRIMARY KEY,
        manifest_hash varchar(64) NOT NULL UNIQUE,
        preview_hash varchar(64) NOT NULL,
        reviewed_by varchar(250) NOT NULL,
        reason text NOT NULL,
        manifest jsonb NOT NULL,
        resource_count bigint NOT NULL,
        preserved_imports bigint NOT NULL,
        preserved_selections bigint NOT NULL,
        recorded_at timestamptz NOT NULL DEFAULT clock_timestamp()
    )""")
    )
    connection.execute(
        text("""CREATE TABLE resource_set_cutovers (
        resource_id text PRIMARY KEY REFERENCES resources(id),
        cutover_id uuid NOT NULL REFERENCES set_ownership_cutovers(cutover_id),
        lifecycle_id uuid NOT NULL REFERENCES lifecycles(lifecycle_id),
        source_id varchar(128) REFERENCES sources(source_id),
        set_id varchar(128) NOT NULL REFERENCES sets(set_id),
        target_source_id varchar(128) NOT NULL REFERENCES sources(source_id),
        resource_version integer NOT NULL,
        original_updated_at timestamptz NOT NULL,
        reason text NOT NULL,
        source_reconciliation text
    )""")
    )
    connection.execute(
        text(
            "CREATE INDEX resource_set_cutover_scope ON resource_set_cutovers(set_id, lifecycle_id)"
        )
    )
    connection.execute(
        text("""CREATE FUNCTION protect_set_cutover() RETURNS trigger
        LANGUAGE plpgsql AS $$ BEGIN
        RAISE EXCEPTION 'Set ownership cutover evidence is immutable'; END $$""")
    )
    for table in ("set_ownership_cutovers", "resource_set_cutovers"):
        connection.execute(
            text(f"""CREATE TRIGGER protect_set_cutover BEFORE UPDATE OR DELETE
            ON {table} FOR EACH ROW EXECUTE FUNCTION protect_set_cutover()""")
        )


def apply_migration(connection, prepared):
    """Run after new columns/constraints exist, before Source provenance is renamed."""
    approval, result = prepared
    manifest = approval.manifest
    cutover_id = uuid5(NAMESPACE_URL, "geomg-set-cutover:" + result["preview_hash"])
    actor_id = uuid5(NAMESPACE_URL, "geomg-system:set-ownership-cutover:0022")
    connection.execute(
        text("""INSERT INTO actors(id, subject_key, kind, display_name)
        VALUES (:id, 'set-ownership-cutover:0022', 'system', 'Set ownership migration')
        ON CONFLICT (id) DO NOTHING"""),
        {"id": actor_id},
    )

    def event(kind, identifier, action, details):
        identity = "source_id" if kind == "source" else "set_id"
        connection.execute(
            text(f"""INSERT INTO lifecycle_activity_entries
            (id, {identity}, actor_id, actor_display_name, action, software_version,
             correlation_id, idempotency_key, reason, details, origin)
            VALUES (:id, :subject, :actor, 'Set ownership migration', :action, '0022',
                    :cutover, :key, :reason, CAST(:details AS jsonb), 'schema-migration')"""),
            {
                "id": uuid5(cutover_id, action + ":" + identifier),
                "subject": identifier,
                "actor": actor_id,
                "action": action,
                "cutover": cutover_id,
                "key": uuid5(cutover_id, kind + ":" + identifier),
                "reason": approval.reason,
                "details": encoded(
                    {
                        "cutover_id": str(cutover_id),
                        "reviewed_by": approval.reviewed_by,
                        "manifest_hash": result["manifest_hash"],
                        **details,
                    }
                ),
            },
        )

    for table, definitions in (("sources", manifest.new_sources), ("sets", manifest.new_sets)):
        for definition in definitions:
            values = definition.model_dump(mode="json")
            values.update(created_by_actor_id=actor_id, updated_by_actor_id=actor_id)
            names = ", ".join(values)
            parameters = ", ".join(":" + name for name in values)
            # Column names come exclusively from fixed Pydantic models above.
            connection.execute(text(f"INSERT INTO {table} ({names}) VALUES ({parameters})"), values)
            kind = "source" if table == "sources" else "set"
            event(kind, values[kind + "_id"], kind + ".created", {})
    connection.execute(
        text("""INSERT INTO set_ownership_cutovers
        (cutover_id, manifest_hash, preview_hash, reviewed_by, reason, manifest,
         resource_count, preserved_imports, preserved_selections)
        VALUES (:id, :manifest_hash, :preview_hash, :reviewed_by, :reason,
                CAST(:manifest AS jsonb), :resource_count,
                :preserved_imports, :preserved_selections)"""),
        {
            "id": cutover_id,
            "manifest_hash": result["manifest_hash"],
            "preview_hash": result["preview_hash"],
            "reviewed_by": approval.reviewed_by,
            "reason": approval.reason,
            "manifest": encoded(manifest.model_dump(mode="json")),
            "resource_count": result["resource_count"],
            "preserved_imports": result["preserved_imports"],
            "preserved_selections": result["preserved_selections"],
        },
    )
    connection.execute(
        text(
            MAPPING
            + """INSERT INTO resource_set_cutovers
        (resource_id, cutover_id, lifecycle_id, source_id, set_id, target_source_id,
         resource_version, original_updated_at, reason, source_reconciliation)
        SELECT m.id, :cutover, m.lifecycle_id, m.source_id, m.target_set_id, s.source_id,
               m.lock_version, m.original_updated_at, m.reason, m.source_reconciliation
        FROM matched m JOIN sets s ON s.set_id = m.target_set_id
    """
        ),
        {"mapping": mappings(manifest), "cutover": cutover_id},
    )
    connection.execute(
        text("""UPDATE resources r SET set_id = c.set_id,
        lock_version = r.lock_version + 1, updated_at = clock_timestamp()
        FROM resource_set_cutovers c WHERE c.resource_id = r.id AND c.cutover_id = :cutover"""),
        {"cutover": cutover_id},
    )
    migrated = connection.scalar(
        text("SELECT count(*) FROM resource_set_cutovers WHERE cutover_id = :id"),
        {"id": cutover_id},
    )
    if migrated != result["resource_count"]:
        raise ValueError("Cutover Resource totals did not reconcile")
    for row in connection.execute(
        text("""SELECT set_id, count(*) AS resource_count,
            array_agg(DISTINCT lifecycle_id::text ORDER BY lifecycle_id::text)
                AS legacy_lifecycle_ids
            FROM resource_set_cutovers GROUP BY set_id ORDER BY set_id""")
    ).mappings():
        event("set", row["set_id"], "set.migrated", dict(row))


def applied_receipt(connection, manifest, preview_hash):
    revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
    scripts = ScriptDirectory.from_config(migration_config(connection))
    if not any(item.revision == "0022" for item in scripts.iterate_revisions(revision, "base")):
        return None
    receipt = (
        connection.execute(
            text("""SELECT cutover_id::text, manifest_hash, preview_hash,
        resource_count, preserved_imports, preserved_selections, reviewed_by
        FROM set_ownership_cutovers
        WHERE manifest_hash = :hash AND preview_hash = :preview"""),
            {
                "hash": digest(manifest.model_dump(mode="json")),
                "preview": preview_hash,
            },
        )
        .mappings()
        .first()
    )
    if receipt is None:
        raise ValueError(
            "Database already uses Set ownership; this reviewed cutover was not applied"
        )
    return {"already_applied": True, **dict(receipt)}


def migration_config(connection):
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "migrations"))
    config.attributes["connection"] = connection
    return config


async def run(args):
    settings = get_settings()
    if settings.app_env not in {"development", "test"}:
        raise ValueError("Production cutover requires closed DEC-005/DEC-009 gates")
    manifest = None
    if args.operation != "inventory":
        manifest = Manifest.model_validate(json.loads(args.manifest.read_text()))
    engine = create_async_engine(settings.database_url)
    try:
        async with engine.begin() as connection:
            if args.operation != "apply":
                await connection.execute(
                    text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
                )
            if args.operation == "inventory":
                result = await connection.run_sync(snapshot)
                result["draft_manifest"] = draft(result)
            elif args.operation == "preview":
                result = await connection.run_sync(lambda sync: preview(sync, manifest))
            else:
                if not args.reviewed_by.strip() or not args.reason.strip():
                    raise ValueError("Apply requires a named reviewer and a nonblank reason")

                def migrate(sync):
                    replay = applied_receipt(sync, manifest, args.preview_hash)
                    if replay is not None:
                        return replay
                    config = migration_config(sync)
                    config.attributes["set_cutover"] = {
                        "manifest": manifest.model_dump(mode="json"),
                        "preview_hash": args.preview_hash,
                        "reviewed_by": args.reviewed_by,
                        "reason": args.reason,
                    }
                    # This approval covers only the ownership cutover, even if
                    # later releases add unrelated migrations after it.
                    command.upgrade(config, "0022")
                    return {"applied": True, **applied_receipt(sync, manifest, args.preview_hash)}

                result = await connection.run_sync(migrate)
        args.output.write_text(json.dumps(result, indent=2) + "\n")
        return 0 if result.get("ready", True) else 1
    finally:
        await engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="operation", required=True)
    for name in ("inventory", "preview", "apply"):
        sub = commands.add_parser(name)
        sub.add_argument("--output", required=True, type=Path)
        if name != "inventory":
            sub.add_argument("--manifest", required=True, type=Path)
        if name == "apply":
            sub.add_argument("--preview-hash", required=True)
            sub.add_argument("--reviewed-by", required=True)
            sub.add_argument("--reason", required=True)
    return asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
