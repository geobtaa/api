from types import SimpleNamespace
from unittest.mock import patch

import pytest

import scripts.refresh_resource_caches as refresh_resource_caches


class FakeDatabase:
    def __init__(self, *, is_connected: bool):
        self.is_connected = is_connected
        self.connect_count = 0
        self.disconnect_count = 0

    async def connect(self):
        self.connect_count += 1
        self.is_connected = True

    async def disconnect(self):
        self.disconnect_count += 1
        self.is_connected = False


class FakeAsyncClient:
    def __init__(self, **kwargs):
        self.database = kwargs.pop("database")
        self.kwargs = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, path, *, headers):
        assert self.database.is_connected is True
        return SimpleNamespace(status_code=200)


@pytest.mark.asyncio
async def test_warm_endpoint_caches_connects_database_before_concurrent_requests():
    fake_database = FakeDatabase(is_connected=False)

    def fake_client(**kwargs):
        return FakeAsyncClient(database=fake_database, **kwargs)

    with (
        patch.object(refresh_resource_caches, "database", fake_database),
        patch.object(refresh_resource_caches.httpx, "ASGITransport", return_value=object()),
        patch.object(refresh_resource_caches.httpx, "AsyncClient", side_effect=fake_client),
    ):
        stats = await refresh_resource_caches.warm_endpoint_caches(
            ["parent"],
            tagged_paths=[],
            include_tagged_paths=False,
            max_paths=10,
            concurrency=2,
            timeout_seconds=5,
        )

    assert stats == {"attempted": 2, "warmed": 2, "errors": 0}
    assert fake_database.connect_count == 1
    assert fake_database.disconnect_count == 1


@pytest.mark.asyncio
async def test_warm_endpoint_caches_leaves_existing_database_pool_open():
    fake_database = FakeDatabase(is_connected=True)

    with (
        patch.object(refresh_resource_caches, "database", fake_database),
        patch.object(refresh_resource_caches.httpx, "ASGITransport", return_value=object()),
        patch.object(
            refresh_resource_caches.httpx,
            "AsyncClient",
            side_effect=lambda **kwargs: FakeAsyncClient(database=fake_database, **kwargs),
        ),
    ):
        await refresh_resource_caches.warm_endpoint_caches(
            ["parent"],
            tagged_paths=[],
            include_tagged_paths=False,
            max_paths=10,
            concurrency=2,
            timeout_seconds=5,
        )

    assert fake_database.connect_count == 0
    assert fake_database.disconnect_count == 0


@pytest.mark.asyncio
async def test_warm_endpoint_caches_disconnects_database_after_client_failure():
    fake_database = FakeDatabase(is_connected=False)

    with (
        patch.object(refresh_resource_caches, "database", fake_database),
        patch.object(refresh_resource_caches.httpx, "ASGITransport", return_value=object()),
        patch.object(
            refresh_resource_caches.httpx,
            "AsyncClient",
            side_effect=RuntimeError("client setup failed"),
        ),
    ):
        with pytest.raises(RuntimeError, match="client setup failed"):
            await refresh_resource_caches.warm_endpoint_caches(
                ["parent"],
                tagged_paths=[],
                include_tagged_paths=False,
                max_paths=10,
                concurrency=2,
                timeout_seconds=5,
            )

    assert fake_database.disconnect_count == 1
