from dataclasses import replace
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import httpx2
import pytest
from sqlalchemy import func, select, text, update
from test_api import make_settings
from test_managing_sets import create, headers
from test_resources import api as resource_api

from app.identity.service import token_hash
from app.main import create_app
from app.resources.alpha_bridge import Batch, ingest, reviews
from app.resources.models import distributions, resources

api = resource_api
pytestmark = pytest.mark.integration


async def test_scoped_bridge_conflicts_deletions_pilot_and_replay(api, database_engine):
    client, actors = api
    scope = await create(client)
    async with database_engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO alpha_bridge_membership VALUES('record',:s,'production'),"
                "('pilot',:s,'pilot')"
            ),
            {"s": scope["set_id"]},
        )
    record = {
        "id": "record",
        "dct_title_s": "Original",
        "publication_state": "published",
        "gbl_mdModified_dt": "2026-11-20T00:00:00Z",
        "kithe_updated_at": "2026-11-20T00:00:00Z",
        "assets": [],
        "document_data_dictionaries": [],
        "document_data_dictionary_entries": [],
        "document_downloads": [],
        "document_distributions": [
            {"id": 73, "reference_type_id": 7, "url": "https://example.org"}
        ],
        "document_licensed_accesses": [],
    }
    batch = Batch(
        records=[
            record,
            {**record, "id": "pilot"},
            {**record, "id": "unassigned"},
            {**record, "id": "gone", "deleted": True},
        ]
    )
    key = uuid4()
    result = await ingest(database_engine, batch, key, "alpha")
    assert [i.outcome for i in result.items] == [
        "created",
        "pilot_review",
        "intake",
        "deletion_review",
    ]
    assert result == await ingest(database_engine, batch, key, "alpha")
    second = {**record, "dct_title_s": "Upstream edit", "kithe_updated_at": "2026-11-20T00:05:00Z"}
    result = await ingest(database_engine, Batch(records=[second]), uuid4(), "alpha")
    assert result.items[0].outcome == "updated"
    async with database_engine.begin() as conn:
        await conn.execute(
            update(resources)
            .where(resources.c.id == "record")
            .values(
                lock_version=3,
                dct_title_s="Staff edit",
                gbl_mdModified_dt=datetime(2026, 11, 20, 0, 8),
            )
        )
        await conn.execute(update(distributions).values(label="Staff label"))
    clean = {
        **second,
        "dct_subject_sm": ["Maps"],
        "gbl_mdModified_dt": "2026-11-20T00:07:00Z",
        "kithe_updated_at": "2026-11-20T00:07:00Z",
        "document_data_dictionaries": [{"id": 15, "name": "New dictionary"}],
    }
    result = await ingest(database_engine, Batch(records=[clean]), uuid4(), "alpha")
    assert result.items[0].outcome == "updated"
    result = await ingest(
        database_engine,
        Batch(
            records=[
                {**second, "dct_title_s": "Third title", "kithe_updated_at": "2026-11-20T00:10:00Z"}
            ]
        ),
        uuid4(),
        "alpha",
    )
    assert result.items[0].outcome == "conflict"
    async with database_engine.connect() as conn:
        assert (
            await conn.scalar(select(resources.c.dct_title_s).where(resources.c.id == "record"))
            == "Staff edit"
        )
        assert (
            await conn.scalar(
                select(func.count()).select_from(resources).where(resources.c.id == "gone")
            )
            == 0
        )
    reviewer = replace(actors[0], set_ids=frozenset([scope["set_id"]]))

    async def visible_reviews():
        return [r["resource_id"] for r in await reviews(database_engine, reviewer, 50, 0)]

    assert "record" in await visible_reviews()
    async with database_engine.begin() as conn:
        assert await conn.scalar(select(distributions.c.label)) == "Staff label"
        assert await conn.scalar(select(resources.c.gbl_mdModified_dt)) == datetime(
            2026, 11, 20, 0, 8
        )
        await conn.execute(update(resources).where(resources.c.id == "record").values(set_id=None))
    assert "record" not in await visible_reviews()
    settings = replace(
        make_settings(),
        app_env="dev2",
        auth_mode="local-password",
        bridge_token_sha256=token_hash("test-key"),
        bridge_token_expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    app = create_app(settings=settings)
    app.state.database_engine = database_engine
    path = "/api/v1/admin/intake/bridge-batches"
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=app), base_url="https://admin.test"
    ) as candidate:
        assert (
            await candidate.post(path, json=batch.model_dump(), headers=headers(key))
        ).status_code == 403
        accepted = await candidate.post(
            path,
            json=batch.model_dump(),
            headers={**headers(key), "X-GEOMG-Bridge-Token": "test-key"},
        )
        assert accepted.status_code == 200, accepted.text
