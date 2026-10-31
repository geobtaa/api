"""Opt-in local PostgreSQL checks. All test DDL/data rolls back with its transaction."""

import asyncio
import os
import uuid

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url

from app.services.preview_assets.models import Layer, Manifest, Outcome
from app.services.preview_assets.repository import (
    hydrate_sources,
    published_for,
    record_signature,
    save_attempt,
)
from db.models import (
    distribution_types,
    resource_assets,
    resource_distributions,
    resource_preview_assets,
    resources,
)


def test_publication_retention_and_source_withdrawal(monkeypatch):
    url = os.getenv("PREVIEW_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set PREVIEW_TEST_DATABASE_URL to a local PostgreSQL database")
    assert make_url(url).host in {"localhost", "127.0.0.1", "::1"}
    monkeypatch.setenv("PREVIEW_ASSETS_ENABLED", "true")
    monkeypatch.setenv("PREVIEW_APPROVED_RESOURCE_IDS", "test")
    schema = "preview_test_" + uuid.uuid4().hex
    engine = create_engine(url)
    with engine.connect() as base:
        transaction = base.begin()
        try:
            base.execute(text(f"CREATE SCHEMA {schema}"))
            connection = base.execution_options(schema_translate_map={None: schema})
            for table in [
                resources,
                distribution_types,
                resource_distributions,
                resource_assets,
                resource_preview_assets,
            ]:
                table.create(connection)
            record = {
                "id": "test",
                "dct_accessRights_s": "Public",
                "publication_state": "published",
            }
            connection.execute(resources.insert().values(**record))
            connection.execute(
                resource_assets.insert().values(
                    resource_id="test",
                    dct_references_uri_key="http://schema.org/downloadUrl",
                    file_url="https://example.org/a.zip",
                )
            )
            record = hydrate_sources(
                connection, connection.execute(select(resources)).mappings().one()
            )
            signature = record_signature(record)
            good = Manifest(
                status=Outcome.READY,
                layers=[
                    Layer(
                        id="one",
                        name="one",
                        format="pmtiles",
                        url="https://example.org/prepared.pmtiles",
                    )
                ],
            )
            save_attempt(connection, "test", signature, good)

            class Session:
                async def execute(self, query):
                    return connection.execute(query)

            assert asyncio.run(published_for("test", Session()))["status"] == "ready"
            child = {**record, "id": "child", "_preview_sources": []}
            connection.execute(
                resources.insert().values(
                    id="child", dct_accessRights_s="Public", publication_state="published"
                )
            )
            child = hydrate_sources(
                connection,
                connection.execute(select(resources).where(resources.c.id == "child"))
                .mappings()
                .one(),
            )
            good.dependencies = [{"resource_id": "child", "signature": record_signature(child)}]
            save_attempt(connection, "test", signature, good)
            assert asyncio.run(published_for("test", Session()))["layers"]
            connection.execute(
                resources.update()
                .where(resources.c.id == "child")
                .values(dct_accessRights_s="Restricted")
            )
            assert asyncio.run(published_for("test", Session())) is None
            connection.execute(
                resources.update()
                .where(resources.c.id == "child")
                .values(dct_accessRights_s="Public")
            )
            save_attempt(connection, "test", signature, Manifest(status=Outcome.UNAVAILABLE))
            assert asyncio.run(published_for("test", Session()))["layers"]
            connection.execute(
                resource_assets.delete().where(resource_assets.c.resource_id == "test")
            )
            assert asyncio.run(published_for("test", Session())) is None
            connection.execute(
                resources.update()
                .where(resources.c.id == "test")
                .values(dct_accessRights_s="Restricted")
            )
            assert asyncio.run(published_for("test", Session())) is None
        finally:
            transaction.rollback()
    engine.dispose()
