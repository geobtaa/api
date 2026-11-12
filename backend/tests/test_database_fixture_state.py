"""Regression coverage for database pool ownership across fixture invocations."""

from pathlib import Path
from unittest.mock import AsyncMock

import pytest


@pytest.mark.asyncio
@pytest.mark.parametrize("initially_connected", [True, False])
async def test_database_fixture_reuses_pool_on_same_loop(monkeypatch, request, initially_connected):
    import db.database as database_module

    fixture_path = Path(__file__).resolve().parents[1] / "conftest.py"
    fixtures = next(
        plugin
        for plugin in request.config.pluginmanager.get_plugins()
        if getattr(plugin, "__file__", None) == str(fixture_path)
    )

    class FakeDatabase:
        is_connected = initially_connected
        execute = AsyncMock()

        async def connect(self):
            self.is_connected = True

        async def disconnect(self):
            self.is_connected = False

    database = FakeDatabase()
    database.connect = AsyncMock(wraps=database.connect)
    database.disconnect = AsyncMock(wraps=database.disconnect)
    monkeypatch.setattr(database_module, "database", database)
    monkeypatch.setattr(fixtures, "SKIP_TEST_DATABASE", False)
    monkeypatch.setattr(fixtures, "_database_loop_state", fixtures._DatabaseLoopState(loop_id=-1))

    # First use reconnects a pool from another loop, or connects a missing pool.
    # The second fixture invocation on the same loop must reuse that connection.
    for _ in range(2):
        transaction = fixtures.db_transaction.__wrapped__(None)
        assert await transaction.__anext__() is database
        with pytest.raises(StopAsyncIteration):
            await transaction.__anext__()

    database.connect.assert_awaited_once()
    assert database.disconnect.await_count == int(initially_connected)
    statements = [call.args[0] for call in database.execute.await_args_list]
    assert len(statements) == 4
    for savepoint, rollback in zip(statements[::2], statements[1::2]):
        assert rollback == f"ROLLBACK TO {savepoint}"
