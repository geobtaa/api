from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.thumbnail_state_service import (
    ThumbnailState,
    ThumbnailStatePayload,
    ThumbnailStateService,
)


@pytest.mark.asyncio
async def test_thumbnail_success_invalidates_resource_tag():
    payload = ThumbnailStatePayload(
        resource_id="resource-1",
        state=ThumbnailState.SUCCESS,
        source_hash="abc123",
    )
    cache = MagicMock()
    cache.invalidate_tags = AsyncMock(return_value=2)

    with (
        patch("app.services.cache_service.CacheService", return_value=cache),
        patch(
            "app.services.resource_representation_cache.delete_resource_representations",
            new=AsyncMock(return_value={"durable_deleted": True, "redis_deleted": 2}),
        ) as mock_delete_representations,
    ):
        await ThumbnailStateService()._invalidate_success_caches_async(payload)

    mock_delete_representations.assert_awaited_once_with(["resource-1"], cache_service=cache)
    cache.invalidate_tags.assert_awaited_once_with(["resource:resource-1"])


@pytest.mark.asyncio
async def test_thumbnail_non_success_does_not_invalidate_resource_tag():
    payload = ThumbnailStatePayload(
        resource_id="resource-1",
        state=ThumbnailState.QUEUED,
        source_hash="abc123",
    )
    cache = MagicMock()
    cache.invalidate_tags = AsyncMock()

    with patch("app.services.cache_service.CacheService", return_value=cache):
        await ThumbnailStateService()._invalidate_success_caches_async(payload)

    cache.invalidate_tags.assert_not_awaited()


@pytest.mark.parametrize("fail", [False, True])
def test_sync_invalidation_disposes_connections_before_loop_closes(fail):
    import asyncio

    service = ThumbnailStateService()
    payload = ThumbnailStatePayload(
        resource_id="resource-1", state=ThumbnailState.SUCCESS, source_hash="abc123"
    )
    events = []

    async def invalidate(_payload):
        events.append(("invalidate", asyncio.get_running_loop()))
        if fail:
            raise RuntimeError("invalidation failed")

    async def dispose():
        events.append(("dispose", asyncio.get_running_loop()))

    cache = MagicMock()
    cache._redis_client.connection_pool.disconnect = AsyncMock()

    with (
        patch.object(service, "_invalidate_success_caches_async", side_effect=invalidate),
        patch(
            "app.services.thumbnail_state_service._async_engine",
            new=MagicMock(dispose=AsyncMock(side_effect=dispose)),
        ),
        patch("app.services.cache_service.CacheService", return_value=cache),
    ):
        for _ in range(2):
            if fail:
                with pytest.raises(RuntimeError, match="invalidation failed"):
                    service._invalidate_success_caches_sync(payload)
            else:
                service._invalidate_success_caches_sync(payload)

    assert [name for name, _ in events] == ["invalidate", "dispose", "invalidate", "dispose"]
    assert events[0][1] is events[1][1]
    assert events[2][1] is events[3][1]
    assert events[0][1] is not events[2][1]
    assert all(loop.is_closed() for _, loop in events)
    assert cache._redis_client.connection_pool.disconnect.await_count == 2


@pytest.mark.asyncio
async def test_sync_invalidation_preserves_callers_running_loop():
    import asyncio

    service = ThumbnailStateService()
    payload = ThumbnailStatePayload(
        resource_id="resource-1", state=ThumbnailState.SUCCESS, source_hash="abc123"
    )
    finished = asyncio.Event()

    async def invalidate(_payload):
        finished.set()

    engine = MagicMock(dispose=AsyncMock())
    with (
        patch.object(service, "_invalidate_success_caches_async", side_effect=invalidate),
        patch("app.services.thumbnail_state_service._async_engine", engine),
    ):
        service._invalidate_success_caches_sync(payload)
        await asyncio.wait_for(finished.wait(), timeout=1)

    engine.dispose.assert_not_awaited()
    assert not asyncio.get_running_loop().is_closed()
