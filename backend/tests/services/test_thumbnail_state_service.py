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
