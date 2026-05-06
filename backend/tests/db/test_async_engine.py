import pytest
from sqlalchemy.pool import NullPool

from db.async_engine import create_app_async_engine


@pytest.mark.asyncio
async def test_create_app_async_engine_forces_nullpool_in_tests(monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("SQLALCHEMY_ASYNC_USE_NULLPOOL", "false")

    engine = create_app_async_engine(
        "postgresql+asyncpg://postgres:postgres@localhost:2345/btaa_geospatial_api_test"
    )

    try:
        assert isinstance(engine.sync_engine.pool, NullPool)
    finally:
        await engine.dispose()
