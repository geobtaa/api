import pytest
from sqlalchemy.pool import NullPool

from db.async_engine import create_app_async_engine
from db.sync_engine import create_app_sync_engine


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


def test_create_app_sync_engine_forces_nullpool_in_tests(monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("SQLALCHEMY_SYNC_USE_NULLPOOL", "false")

    engine = create_app_sync_engine(
        "postgresql://postgres:postgres@localhost:2345/btaa_geospatial_api_test"
    )

    try:
        assert isinstance(engine.pool, NullPool)
    finally:
        engine.dispose()


def test_create_app_sync_engine_uses_env_pool_bounds(monkeypatch):
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.setattr("db.sync_engine._running_under_pytest", lambda: False)
    monkeypatch.setenv("SQLALCHEMY_SYNC_USE_NULLPOOL", "false")
    monkeypatch.setenv("SQLALCHEMY_SYNC_POOL_SIZE", "2")
    monkeypatch.setenv("SQLALCHEMY_SYNC_MAX_OVERFLOW", "0")
    monkeypatch.setenv("SQLALCHEMY_SYNC_POOL_TIMEOUT", "3")

    engine = create_app_sync_engine(
        "postgresql://postgres:postgres@localhost:2345/btaa_geospatial_api_test"
    )

    try:
        assert engine.pool.size() == 2
        assert engine.pool._max_overflow == 0
        assert engine.pool._timeout == 3
    finally:
        engine.dispose()
