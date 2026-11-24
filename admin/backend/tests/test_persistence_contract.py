from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from test_api import make_settings
from test_sets import EDITOR

from app.config import get_test_database_url
from app.main import create_app
from app.sets.schemas import SetCreate


def test_integration_url_is_explicit_and_local(monkeypatch):
    monkeypatch.delenv("TEST_DATABASE_URL", raising=False)
    assert get_test_database_url() is None
    monkeypatch.setenv("TEST_DATABASE_URL", "postgresql+asyncpg://localhost/production")
    with pytest.raises(ValueError, match="local geomg_test"):
        get_test_database_url()


@pytest.mark.integration
@pytest.mark.parametrize("starting_revision", ["bulk_edits_01", "resource_create_01"])
async def test_resource_migration_heads_converge(database_engine, starting_revision):
    from alembic import command
    from conftest import alembic_config
    from sqlalchemy import text

    async with database_engine.begin() as conn:

        def upgrade_from_branch(sync):
            config = alembic_config(sync)
            command.downgrade(config, "intake_02")
            command.upgrade(config, starting_revision)
            version = text("SELECT version_num FROM alembic_version")
            assert sync.execute(version).scalars().all() == [starting_revision]
            command.upgrade(config, "resource_edits_merge")
            assert sync.execute(version).scalars().all() == ["resource_edits_merge"]

        await conn.run_sync(upgrade_from_branch)
        assert await conn.scalar(text("SELECT to_regclass('resource_bulk_actions') IS NOT NULL"))
        check = await conn.scalar(
            text(
                "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                "WHERE conrelid = 'lifecycle_activity_entries'::regclass "
                "AND conname = 'activity_action'"
            )
        )
        assert "resource.created" in check


def test_production_migrations_are_gated(monkeypatch):
    from alembic import command
    from alembic.config import Config

    from app.config import get_settings

    monkeypatch.setenv("APP_ENV", "production")
    get_settings.cache_clear()
    try:
        config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
        with pytest.raises(RuntimeError, match="DEC-005/DEC-009"):
            command.upgrade(config, "head")
    finally:
        get_settings.cache_clear()


@pytest.mark.parametrize("endpoint", ["https://example.org:invalid", "https://example.org/a b"])
def test_invalid_endpoint(endpoint):
    with pytest.raises(ValidationError):
        SetCreate(title="Example", source_id="parent", endpoint_url=endpoint)


def test_unavailable_database_and_unknown_api_route(monkeypatch, tmp_path):
    from app.api import dependencies

    class OfflineEngine:
        disposed = False

        def connect(self):
            raise OSError("private connection details")

        async def dispose(self):
            self.disposed = True

    engine = OfflineEngine()
    monkeypatch.setattr(dependencies, "create_async_engine", lambda *args, **kwargs: engine)

    async def authenticate(_):
        return EDITOR

    app = create_app(settings=make_settings(), authenticator=authenticate, frontend_dist=tmp_path)
    with TestClient(app) as client:
        response = client.get("/api/v1/admin/sets")
        assert response.status_code == 503
        assert "private connection" not in response.text
        assert client.get("/api/v1/missing").status_code == 404
    assert engine.disposed
