import os
from unittest.mock import AsyncMock, Mock

import asyncpg
import httpx
import pytest

from app.services.bridge_sync.client import BridgePage
from app.services.bridge_sync.geomg import sync_candidate
from scripts import project_geomg_edits as projector


def test_bridge_restarts_with_same_receipt_and_separate_watermark(tmp_path, monkeypatch):
    client = Mock(base_url="https://example.test/feed")
    client.fetch_page.side_effect = [
        BridgePage([{"id": "one"}], "next", True),
        BridgePage([{"id": "two"}], None, False),
        BridgePage([], None, False),
    ]
    sent = []

    def send(url, *, json, headers, **kwargs):
        sent.append(headers["Idempotency-Key"])
        if len(sent) == 1:
            raise TimeoutError()
        return Mock(
            status_code=200,
            json=lambda: {
                "batch_id": sent[-1],
                "items": [{"resource_id": r["id"], "outcome": "created"} for r in json["records"]],
            },
        )

    monkeypatch.setattr("app.services.bridge_sync.geomg.requests.post", send)

    def run(candidate="one"):
        return sync_candidate(
            client, "http://candidate/ingest", "test", tmp_path, candidate_id=candidate
        )

    with pytest.raises(TimeoutError):
        run()
    assert run()["counts"] == {"created": 2}
    assert sent[0] == sent[1] != sent[2]
    assert client.fetch_page.call_args_list[1].kwargs["cursor"] == "next"
    with pytest.raises(ValueError, match="different candidate"):
        run("two")
    assert run()["counts"] == {}
    assert client.fetch_page.call_args.kwargs["changed_since"]


@pytest.mark.asyncio
async def test_visible_requires_current_detail_search_and_index(monkeypatch):
    doc = {"id": "record", "meta": {"catalogVersion": 3}}

    async def response(req):
        return httpx.Response(200, json={"data": doc if req.method == "GET" else [doc]})

    es = AsyncMock()
    monkeypatch.setattr(projector, "es", es)
    monkeypatch.setenv("ELASTICSEARCH_INDEX", "geomg_alpha_test")
    async with httpx.AsyncClient(
        base_url="http://candidate", transport=httpx.MockTransport(response)
    ) as client:
        es.get.return_value = {"_source": {"lock_version": 2}}
        assert not await projector.visible(client, "record", 3, published=True, searchable=True)
        es.get.return_value = {"_source": {"lock_version": 3}}
        assert await projector.visible(client, "record", 3, published=True, searchable=True)
        assert not await projector.visible(client, "record", 4, published=True, searchable=True)


@pytest.mark.asyncio
async def test_public_catalog_hides_drafts_before_serving_resource_routes(monkeypatch):
    from contextlib import asynccontextmanager

    from fastapi import FastAPI
    from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine

    from app.api.v1.endpoint_modules import resources as routes

    table = Table(
        "resources",
        MetaData(),
        Column("id", String, primary_key=True),
        Column("publication_state", String),
        Column("lock_version", Integer),
    )
    monkeypatch.setattr(routes, "resources", table)
    monkeypatch.setattr(routes, "GEOMG_CATALOG_ENABLED", True)
    engine = create_engine("sqlite://")
    table.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(
            table.insert(),
            [
                {"id": state, "publication_state": state, "lock_version": 1}
                for state in ("published", "draft", "unpublished", "retired")
            ],
        )
        assert conn.scalars(routes.public_catalog_query(table.c.id)).all() == ["published"]

        @asynccontextmanager
        async def session():
            yield Mock(scalar=AsyncMock(side_effect=conn.scalar))

        monkeypatch.setattr(routes, "get_async_session", session)
        app = FastAPI()
        app.include_router(routes.router)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            for path in (
                "/resources/draft",
                "/resources/retired/links",
                "/resources/unpublished/metadata",
            ):
                assert (await client.get(path)).status_code == 404


@pytest.mark.asyncio
async def test_staff_projection_precedes_bulk_and_honors_retry_lease():
    url = os.getenv("SEARCH_RELEVANCE_TEST_DB_URL")
    if not url:
        pytest.skip("Set SEARCH_RELEVANCE_TEST_DB_URL to an isolated PostgreSQL service")
    connection = await asyncpg.connect(url)
    try:
        await connection.execute("""
            CREATE TEMP TABLE resource_projection_requests (
                resource_id text, resource_version int, visible_at timestamptz,
                next_attempt_at timestamptz, created_at timestamptz DEFAULT now()
            );
            CREATE TEMP TABLE resources (
                id text, lock_version int, publication_state text, gbl_suppressed_b boolean
            );
            CREATE TEMP TABLE alpha_bridge_state (resource_id text, resource_version int);
            INSERT INTO resources VALUES
                ('feed',2,'published',false),('staff',3,'published',false);
            INSERT INTO alpha_bridge_state VALUES ('feed',2),('staff',2);
            INSERT INTO resource_projection_requests(resource_id,resource_version,next_attempt_at)
                VALUES ('feed',2,now()-interval '1 hour'),('staff',3,now());
        """)
        claim = str(projector.CLAIM_NEXT_PROJECTION).replace("public.", "pg_temp.")
        assert (await connection.fetchrow(claim))["resource_id"] == "staff"
        assert (await connection.fetchrow(claim))["resource_id"] == "feed"
        assert await connection.fetchrow(claim) is None
    finally:
        await connection.close()
