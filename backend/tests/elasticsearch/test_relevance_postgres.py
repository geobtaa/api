"""Optional real Postgres checks in a unique schema, never the catalog's resources table."""

import os
from uuid import uuid4

import asyncpg
import pytest
import pytest_asyncio
from databases import Database

from app.elasticsearch import collection_context, index
from scripts import reindex_atomic


@pytest_asyncio.fixture(loop_scope="function")
async def source(monkeypatch):
    url = os.getenv("SEARCH_RELEVANCE_TEST_DB_URL")
    if not url:
        pytest.skip("Set SEARCH_RELEVANCE_TEST_DB_URL to an isolated PostgreSQL service")
    schema = f"relevance_{uuid4().hex}"
    admin = await asyncpg.connect(url)
    await admin.execute(f'CREATE SCHEMA "{schema}"')
    database = Database(url, min_size=1, max_size=2, server_settings={"search_path": schema})
    await database.connect()
    monkeypatch.setattr(collection_context, "database", database)
    monkeypatch.setattr(reindex_atomic, "database", database)
    try:
        await database.execute("""
            CREATE TABLE resources (
                id text PRIMARY KEY, dct_title_s text, "gbl_resourceClass_sm" text[],
                publication_state text, gbl_suppressed_b boolean,
                "pcdm_memberOf_sm" text[], "dct_isPartOf_sm" text[]
            )
        """)
        await database.execute("""
            INSERT INTO resources VALUES
              ('parent', 'Coal maps', ARRAY['Collections'], 'published', false, '{}', '{}'),
              ('child', 'Pittsburgh sheet', ARRAY['Maps'], 'published', false,
               ARRAY['parent'], ARRAY['parent'])
        """)
        yield database, url, schema
    finally:
        await database.disconnect()
        await admin.execute(f'DROP SCHEMA "{schema}" CASCADE')
        await admin.close()


@pytest.mark.asyncio(loop_scope="function")
async def test_real_membership_queries_and_document_parity(source, monkeypatch):
    from unittest.mock import AsyncMock

    database, _, _ = source
    monkeypatch.setattr(index, "get_resource_summaries", AsyncMock(return_value=[]))
    monkeypatch.setattr(index, "get_spatial_facets", AsyncMock(return_value={}))
    monkeypatch.setattr(index, "get_allmaps_overlay_status", AsyncMock(return_value=False))
    child = dict(await database.fetch_one("SELECT * FROM resources WHERE id='child'"))
    single = await index.process_resource(child)
    batch = await index.prepare_bulk_data([child], "unused")
    assert batch == [single]
    assert single["collection_titles"] == ["Coal maps"]
    assert await collection_context.direct_member_ids(["parent"]) == ["child"]
    await database.execute("UPDATE resources SET dct_title_s='New coal title' WHERE id='parent'")
    assert (await index.process_resource(child))["collection_titles"] == ["New coal title"]
    await database.execute("UPDATE resources SET gbl_suppressed_b=true WHERE id='parent'")
    assert (await index.process_resource(child))["collection_titles"] == []
    await database.execute("DELETE FROM resources WHERE id='parent'")
    assert await collection_context.direct_member_ids(["parent"]) == ["child"]
    assert (await index.process_resource(child))["collection_titles"] == []


@pytest.mark.asyncio(loop_scope="function")
async def test_source_row_versions_and_cutover_lock(source):
    database, url, schema = source
    before = await reindex_atomic._source_versions()
    writer = await asyncpg.connect(url, server_settings={"search_path": schema})
    try:
        await writer.execute("SET lock_timeout='100ms'")
        async with database.connection() as connection:
            async with connection.transaction():
                await connection.execute("LOCK TABLE resources IN SHARE MODE")
                assert await writer.fetchval("SELECT count(*) FROM resources") == 2
                with pytest.raises(asyncpg.LockNotAvailableError):
                    await writer.execute("UPDATE resources SET dct_title_s='New' WHERE id='parent'")
                assert await reindex_atomic._source_versions() == before
        await writer.execute("UPDATE resources SET dct_title_s='New' WHERE id='parent'")
        after = await reindex_atomic._source_versions()
        assert after["parent"] != before["parent"]
        assert after["child"] == before["child"]
    finally:
        await writer.close()
