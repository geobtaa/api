import asyncio
import json
from pathlib import Path
from uuid import uuid4

import asyncpg
import pytest
from sqlalchemy.engine import make_url

from app.config import get_test_database_url
from app.resources import unify


@pytest.mark.integration
async def test_adoption_preserves_native_rows_associations_and_dependent_fk():
    url = get_test_database_url()
    if not url:
        pytest.skip("Requires disposable PostgreSQL")
    # The in-place command explicitly targets public. Give it a private disposable
    # database so it exercises that actual entry point and never touches another test.
    base = make_url(url).set(drivername="postgresql")
    control = await asyncpg.connect(base.render_as_string(hide_password=False))
    name = "geomg_test_unify_" + uuid4().hex
    try:
        await control.execute(f'CREATE DATABASE "{name}" TEMPLATE template0')
        conn = await asyncpg.connect(base.set(database=name).render_as_string(hide_password=False))
        try:
            await conn.execute(
                (Path(__file__).parent / "fixtures/data_api_shared_schema.sql").read_text()
            )
            vocab = json.loads((unify.ROOT / "contracts/distribution_types.json").read_text())
            await conn.executemany(
                """INSERT INTO distribution_types(id,name,distribution_type,distribution_uri)
                VALUES($1,$2,$3,$4)""",
                [(x["id"], x["name"], x["distribution_type"], x["uri"]) for x in vocab],
            )
            await conn.execute("""INSERT INTO resources(id,publication_state,dct_title_s)
                VALUES('pilot','published','Pilot title'),('existing','draft','Existing draft'),
                      ('unknown','unpublished','Unmapped');
                CREATE TABLE dependent(record_id varchar REFERENCES resources(id));
                INSERT INTO dependent VALUES('pilot');
                INSERT INTO resource_distributions(resource_id,distribution_type_id,url,
                    position,import_distribution_id)
                VALUES('pilot',1,'https://example.test/2',2,'legacy-2'),
                      ('pilot',1,'https://example.test/1',1,'legacy-1');""")
            before = await unify.inventory(conn, ["pilot"])
            native = await conn.fetchval("SELECT 'public.resources'::regclass::oid")
            scope = {
                "sources": [["s", "Source"]],
                "sets": [["managed", "s", "Set", "active"]],
                "members": [["existing", "managed", "s"]],
            }

            async def run(key=None, connection=conn):
                return await unify.migrate(
                    connection,
                    scope,
                    ["pilot"],
                    "scope",
                    before["pilot_rows"],
                    expected_db=name,
                    confirmation=key,
                )

            preview = await run()
            with pytest.raises(ValueError, match="Preview changed"):
                await run("stale")
            assert not await conn.fetchval("SELECT to_regclass('public.actors') IS NOT NULL")
            async with conn.transaction():
                with pytest.raises(ValueError, match="Set and Source identities"):
                    await unify.migrate(
                        conn,
                        {**scope, "members": [["existing", "managed", "wrong"]]},
                        ["pilot"],
                        "scope",
                        before["pilot_rows"],
                        expected_db=name,
                        confirmation=preview["preview_sha256"],
                    )
            assert not await conn.fetchval("SELECT to_regclass('public.actors') IS NOT NULL")
            second = await asyncpg.connect(
                base.set(database=name).render_as_string(hide_password=False)
            )
            try:
                results = await asyncio.gather(
                    run(preview["preview_sha256"]), run(preview["preview_sha256"], second)
                )
                assert sorted(r["status"] for r in results) == ["already applied", "applied"]
            finally:
                await second.close()
            assert await unify.inventory(conn, ["pilot"]) == before
            assert (await run(preview["preview_sha256"]))["status"] == "already applied"
            assert (
                await conn.fetchval(
                    "SELECT confrelid FROM pg_constraint WHERE conrelid='dependent'::regclass "
                    "AND contype='f'"
                )
                == native
            )
            assert await conn.fetchval("SELECT set_id FROM resources WHERE id='unknown'") is None
            assert (
                await conn.fetchval("SELECT set_id FROM resources WHERE id='existing'") == "managed"
            )
            assert (
                await conn.fetchval("""SELECT t.title FROM resources r JOIN sets s USING(set_id)
                JOIN sources t USING(source_id) WHERE r.id='pilot'""")
                == "Priority 2 Workgroup"
            )
            assert (
                await conn.fetchval(
                    "SELECT count(*) FROM lifecycle_activity_entries "
                    "WHERE action='resources.imported'"
                )
                == 3
            )
        finally:
            await conn.close()
    finally:
        await control.execute(f'DROP DATABASE IF EXISTS "{name}"')
        await control.close()
