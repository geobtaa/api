from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import get_test_database_url


def alembic_config(connection):
    config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
    config.attributes["connection"] = connection
    return config


@pytest.fixture
async def database_engine():
    url = get_test_database_url()
    if not url:
        pytest.skip("Use make backend-test to supply disposable PostgreSQL")
    # Each test gets its own schema; no test truncates a shared or legacy table.
    schema = "test_" + uuid4().hex
    bootstrap = create_async_engine(url)
    async with bootstrap.begin() as connection:
        await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_async_engine(
        url, connect_args={"server_settings": {"search_path": schema, "timezone": "UTC"}}
    )
    try:
        async with engine.begin() as connection:
            await connection.run_sync(lambda sync: command.upgrade(alembic_config(sync), "head"))
        yield engine
    finally:
        await engine.dispose()
        async with bootstrap.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        await bootstrap.dispose()
