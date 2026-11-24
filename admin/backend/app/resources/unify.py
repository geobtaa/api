"""Preview or apply the one-time in-place GEOMG/data-api schema adoption."""

import argparse
import asyncio
import hashlib
import json
from pathlib import Path
from uuid import uuid4

import asyncpg
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[2]
DDL = ROOT / "migrations/catalog/alpha_support.sql"
SHARED = (
    "resources",
    "distribution_types",
    "resource_distributions",
    "resource_relationships",
    "resource_assets",
    "resource_downloads",
    "resource_licensed_accesses",
    "resource_data_dictionaries",
    "resource_data_dictionary_entries",
)
ADDITIONS = [
    "created_at",
    "updated_at",
    "created_by_actor_id",
    "lock_version",
    "set_id",
    "legacy_source_id",
    "lifecycle_id",
]
DEPLOYED_COLUMNS = "3a04d6c17051f3d1b5533cb7236274bca1d5019ba55d1004c87caf2cf396fb13"
REVISION = "unify_catalog_01"


def sha(value):
    return hashlib.sha256(value).hexdigest()


def inputs(scope_file, pilot_file):
    blob = scope_file.read_bytes()
    scope = json.loads(blob)
    pilot = json.loads(pilot_file.read_bytes())
    ids = pilot["ids"]
    if (
        not ids
        or ids != sorted(set(ids))
        or pilot["query"] != "P2-pilot"
        or pilot["sha256"] != sha("\n".join(ids).encode())
    ):
        raise ValueError("Invalid pilot snapshot")
    sources = {sid for sid, _ in scope["sources"]}
    sets = {sid: source for sid, source, _, _ in scope["sets"]}
    if (
        len(sources) != len(scope["sources"])
        or len(sets) != len(scope["sets"])
        or "priority-2-workgroup" in sources
        or "p2-pilot" in sets
        or not set(sets.values()) <= sources
        or len({rid for rid, _, _ in scope["members"]}) != len(scope["members"])
        or any(sets.get(sid) != source for _, sid, source in scope["members"])
    ):
        raise ValueError("Invalid ownership manifest or conflicting pilot identity")
    return scope, sha(blob), ids


async def inventory(conn, ids):
    counts = {t: await conn.fetchval(f"SELECT count(*) FROM public.{t}") for t in SHARED}
    states = await conn.fetch("SELECT publication_state,count(*) FROM public.resources GROUP BY 1")
    if any(r[0] not in {"draft", "published", "unpublished", "retired"} for r in states):
        raise ValueError("Unexpected publication state")
    pilot_associations = {}
    for table in SHARED[2:]:
        predicate = "resource_id=ANY($1::text[])"
        if table == "resource_relationships":
            predicate = "subject_id=ANY($1::text[]) OR object_id=ANY($1::text[])"
        elif table == "resource_data_dictionary_entries":
            predicate = """resource_data_dictionary_id IN
                (SELECT id FROM public.resource_data_dictionaries
                 WHERE resource_id=ANY($1::text[]))"""
        count, digest = await conn.fetchrow(
            f"""SELECT count(*),
            encode(sha256(convert_to(coalesce(string_agg(h,'' ORDER BY h),''),'UTF8')),'hex')
            FROM (SELECT encode(sha256(convert_to(to_jsonb(t)::text,'UTF8')),'hex') h
                  FROM public.{table} t WHERE {predicate}) hashes""",
            ids,
        )
        pilot_associations[table] = [count, digest]
    matches = await conn.fetchrow(
        """
        SELECT count(*) AS n, bool_and(publication_state='published' AND
               gbl_suppressed_b IS NOT TRUE) AS published,
               encode(sha256(convert_to(string_agg(h,'' ORDER BY h),'UTF8')),'hex') AS digest
        FROM (SELECT publication_state,gbl_suppressed_b,
              encode(sha256(convert_to((to_jsonb(r)-$2::text[])::text,'UTF8')),'hex') h
              FROM public.resources r WHERE id=ANY($1::text[])) pilot""",
        ids,
        ADDITIONS,
    )
    if matches["n"] != len(ids) or not matches["published"]:
        raise ValueError("A pilot Resource is missing or its public visibility changed")
    return {
        "counts": counts,
        "publication": dict(states),
        "pilot_associations": pilot_associations,
        "pilot_rows": matches["digest"],
        "pilot_count": len(ids),
    }


async def schema_signature(conn):
    rows = await conn.fetch(
        """SELECT table_name,ordinal_position,column_name,data_type,
                udt_name,is_nullable,coalesce(column_default,'<NULL>')
        FROM information_schema.columns WHERE table_schema='public' AND table_name=ANY($1)
        ORDER BY table_name,ordinal_position""",
        list(SHARED),
    )
    return sha(json.dumps([list(r) for r in rows], separators=(",", ":")).encode())


async def ownership(conn, actor, scope, ids):
    await conn.executemany(
        """INSERT INTO sources(source_id,title,created_by_actor_id,updated_by_actor_id)
           VALUES($1,$2,$3,$3)""",
        [
            (k, title, actor)
            for k, title in [*scope["sources"], ("priority-2-workgroup", "Priority 2 Workgroup")]
        ],
    )
    await conn.executemany(
        """INSERT INTO sets(set_id,source_id,title,status,created_by_actor_id,updated_by_actor_id)
           VALUES($1,$2,$3,$4,$5,$5)""",
        [
            (k, source, title, status, actor)
            for k, source, title, status in [
                *scope["sets"],
                ("p2-pilot", "priority-2-workgroup", "P2-pilot", "active"),
            ]
        ],
    )
    await conn.execute("""CREATE TEMP TABLE reviewed_scope(
        resource_id text PRIMARY KEY,set_id text NOT NULL,source_id text NOT NULL)
        ON COMMIT DROP""")
    await conn.copy_records_to_table("reviewed_scope", records=scope["members"])
    if await conn.fetchval("""SELECT EXISTS(SELECT FROM reviewed_scope m
        LEFT JOIN sets s USING(set_id)
        WHERE s.source_id IS DISTINCT FROM m.source_id)"""):
        raise ValueError("Reviewed Set and Source identities disagree")
    await conn.execute("""INSERT INTO alpha_bridge_membership
        SELECT resource_id,set_id,'production' FROM reviewed_scope""")
    await conn.execute(
        """INSERT INTO alpha_bridge_membership
        SELECT unnest($1::text[]),'p2-pilot','pilot'
        ON CONFLICT(resource_id) DO UPDATE SET origin='pilot'""",
        ids,
    )


async def migrate(conn, scope, ids, scope_hash, pilot_hash, *, expected_db, confirmation=None):
    # Apply must see commits made while waiting for the advisory/catalog locks.
    # Preview has no locks and needs a single consistent snapshot.
    isolation = "repeatable_read" if confirmation is None else "read_committed"
    async with conn.transaction(isolation=isolation, readonly=confirmation is None):
        await conn.execute("SET LOCAL search_path TO public,pg_catalog")
        if await conn.fetchval("SELECT current_database()") != expected_db:
            raise ValueError("Database differs from the intended target")
        if confirmation:
            await conn.execute("SET LOCAL lock_timeout = '5s'")
            await conn.execute("SELECT pg_advisory_xact_lock(572911632)")
        if await conn.fetchval("SELECT to_regclass('public.alpha_catalog_seed') IS NOT NULL"):
            previous = await conn.fetchrow("SELECT * FROM alpha_catalog_seed WHERE singleton")
            if not previous or (previous["scope_hash"], previous["pilot_hash"]) != (
                scope_hash,
                pilot_hash,
            ):
                raise ValueError("Unrecognized prior adoption")
            if await conn.fetchval("SELECT version_num FROM geomg_alembic_version") != REVISION:
                raise ValueError("Existing GEOMG schema version differs")
            return {"status": "already applied", "pilot_count": previous["pilot_count"]}
        if confirmation:
            # Keep the preview, catalog rows and evidence consistent through commit.
            await conn.execute(
                "LOCK TABLE "
                + ",".join("public." + t for t in sorted(SHARED))
                + " IN SHARE ROW EXCLUSIVE MODE"
            )
        if await schema_signature(conn) != DEPLOYED_COLUMNS:
            raise ValueError("Shared catalog differs from the deployed schema comparison")
        vocab = json.loads((ROOT / "contracts/distribution_types.json").read_text())
        actual = await conn.fetch(
            "SELECT id,name,distribution_uri FROM distribution_types ORDER BY id"
        )
        if [tuple(r) for r in actual] != [(r["id"], r["name"], r["uri"]) for r in vocab]:
            raise ValueError("Distribution vocabulary differs")
        before = await inventory(conn, ids)
        if before["pilot_rows"] != pilot_hash:
            raise ValueError("Pilot metadata differs from the reviewed checksum")
        matched = await conn.fetchval(
            "SELECT count(*) FROM resources WHERE id=ANY($1::text[])",
            [rid for rid, _, _ in scope["members"]],
        )
        fingerprint = sha(
            json.dumps(
                [
                    expected_db,
                    REVISION,
                    sha(DDL.read_bytes()),
                    scope_hash,
                    matched,
                    sha("\n".join(ids).encode()),
                    before,
                ],
                sort_keys=True,
            ).encode()
        )
        if not confirmation:
            return {
                **before,
                "scope_assignments": len(scope["members"]),
                "existing_resources_with_reviewed_mapping": matched,
                "preview_sha256": fingerprint,
            }
        if confirmation != fingerprint:
            raise ValueError("Preview changed; reconcile before applying")
        await conn.execute(DDL.read_text())
        actor = uuid4()
        await conn.execute(
            """INSERT INTO actors(id,subject_key,kind,display_name)
          VALUES($1,'kithe-production-bridge','service_account','Production Kithe Bridge')""",
            actor,
        )
        await ownership(conn, actor, scope, ids)
        # PostgreSQL uses one constant default for the adopted rows. Keep the
        # importer default for compatibility with pre-alpha inserts on rollback.
        await conn.execute(f"""ALTER TABLE public.resources
          ADD lifecycle_id uuid REFERENCES lifecycles(lifecycle_id),
          ADD legacy_source_id varchar(128) REFERENCES sources(source_id),
          ADD set_id varchar(128) REFERENCES sets(set_id),
          ADD lock_version integer NOT NULL DEFAULT 1 CHECK(lock_version>0),
          ADD created_at timestamptz NOT NULL DEFAULT now(),
          ADD updated_at timestamptz NOT NULL DEFAULT now(),
          ADD created_by_actor_id uuid NOT NULL DEFAULT '{actor}'::uuid REFERENCES actors(id);
          CREATE INDEX resources_set_title ON resources(set_id,dct_title_s,id);
          CREATE INDEX resources_lifecycle_title ON resources(lifecycle_id,dct_title_s,id);
          CREATE INDEX resources_legacy_source_id ON resources(legacy_source_id);
          ALTER TABLE distribution_types ADD UNIQUE(distribution_uri);""")
        await conn.execute("""UPDATE resources r SET set_id=m.set_id
           FROM alpha_bridge_membership m WHERE m.resource_id=r.id""")
        await conn.execute(
            """INSERT INTO lifecycle_activity_entries(id,set_id,resource_id,actor_id,
          actor_display_name,action,software_version,correlation_id,idempotency_key,details)
          SELECT gen_random_uuid(),set_id,id,$1,'Production Kithe Bridge','resources.imported',
          'unify_catalog_01',$2,gen_random_uuid(),jsonb_build_object('origin','dev2-adoption',
          'resource_version',1) FROM resources""",
            actor,
            uuid4(),
        )
        if await inventory(conn, ids) != before:
            raise ValueError("Catalog counts, publication states or pilot metadata changed")
        if await conn.fetchval(
            """SELECT EXISTS(SELECT FROM resources r
           LEFT JOIN alpha_bridge_membership m ON m.resource_id=r.id
           WHERE r.set_id IS DISTINCT FROM m.set_id OR r.lock_version<>1
           OR r.created_by_actor_id<>$1)""",
            actor,
        ):
            raise ValueError("Ownership and version reconciliation failed")
        await conn.execute(
            """INSERT INTO alpha_catalog_seed(singleton,scope_hash,pilot_hash,pilot_count)
            VALUES(true,$1,$2,$3)""",
            scope_hash,
            pilot_hash,
            len(ids),
        )
        await conn.execute(
            "CREATE TABLE geomg_alembic_version(version_num varchar(32) PRIMARY KEY)"
        )
        await conn.execute("INSERT INTO geomg_alembic_version VALUES($1)", REVISION)
        return {**before, "status": "applied", "preview_sha256": fingerprint}


async def main(args):
    from app.config import get_settings

    settings = get_settings()
    if settings.app_env not in {"dev2", "test"}:
        raise ValueError("Catalog adoption requires the dev2 or disposable test environment")
    scope, scope_hash, ids = inputs(args.scope, args.pilot)
    url = make_url(settings.database_url).set(drivername="postgresql")
    conn = await asyncpg.connect(url.render_as_string(hide_password=False))
    try:
        print(
            json.dumps(
                await migrate(
                    conn,
                    scope,
                    ids,
                    scope_hash,
                    args.pilot_row_sha256,
                    expected_db=args.database_name,
                    confirmation=args.apply,
                ),
                indent=2,
            )
        )
    finally:
        await conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-name", required=True)
    parser.add_argument("--scope", type=Path, required=True)
    parser.add_argument("--pilot", type=Path, required=True)
    parser.add_argument("--pilot-row-sha256", required=True)
    parser.add_argument("--apply", metavar="PREVIEW_SHA256")
    asyncio.run(main(parser.parse_args()))
