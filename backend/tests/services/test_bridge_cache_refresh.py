from unittest.mock import AsyncMock, patch

import pytest

import app.services.bridge_sync.cache_refresh as cache_refresh


class FakeCacheService:
    def __init__(self):
        self.cached_records_calls = []
        self.invalidate_calls = []

    async def cached_records_for_tags(self, tags):
        self.cached_records_calls.append(list(tags))
        return [
            {
                "warm": {
                    "method": "GET",
                    "path": "/api/v1/search",
                    "query": "q=bridged",
                }
            }
        ]

    async def invalidate_tags(self, tags):
        self.invalidate_calls.append(list(tags))
        return 3


@pytest.mark.asyncio
async def test_refresh_cache_for_changed_resources_deletes_durable_and_warms_assets(
    monkeypatch,
):
    fake_cache = FakeCacheService()
    monkeypatch.setattr(cache_refresh, "ENDPOINT_CACHE", True)
    monkeypatch.setenv("BRIDGE_CACHE_REFRESH_ENABLED", "true")
    monkeypatch.setenv("BRIDGE_CACHE_REWARM_MAX_URLS", "0")

    with (
        patch.object(cache_refresh, "CacheService", return_value=fake_cache),
        patch.object(
            cache_refresh,
            "delete_resource_representations",
            new=AsyncMock(return_value={"durable_deleted": True, "redis_deleted": 2}),
        ) as mock_delete_representations,
        patch.object(
            cache_refresh,
            "_warm_generated_assets_for_changed_resources",
            new=AsyncMock(return_value={"enabled": True, "resources": 1}),
        ) as mock_warm_assets,
    ):
        stats = await cache_refresh.refresh_cache_for_changed_resources(
            ["resource-1", "resource-1"]
        )

    assert stats["enabled"] is True
    assert stats["resource_ids"] == 1
    assert stats["invalidated"] == 3
    assert stats["resource_representations_deleted"] == {
        "durable_deleted": True,
        "redis_deleted": 2,
    }
    assert stats["generated_assets"] == {"enabled": True, "resources": 1}
    assert stats["warm_urls"] == 0
    mock_delete_representations.assert_awaited_once_with(
        ["resource-1"],
        cache_service=fake_cache,
    )
    mock_warm_assets.assert_awaited_once_with(["resource-1"])
    assert fake_cache.cached_records_calls == [["resource:resource-1"]]
    assert fake_cache.invalidate_calls == [["resource:resource-1"]]


@pytest.mark.asyncio
async def test_refresh_cache_for_changed_resources_invalidates_every_changed_id(
    monkeypatch,
):
    fake_cache = FakeCacheService()
    monkeypatch.setattr(cache_refresh, "ENDPOINT_CACHE", True)
    monkeypatch.setenv("BRIDGE_CACHE_REFRESH_ENABLED", "true")
    monkeypatch.setenv("BRIDGE_CACHE_REFRESH_MAX_RESOURCE_IDS", "1")
    monkeypatch.setenv("BRIDGE_CACHE_REWARM_MAX_URLS", "0")

    with (
        patch.object(cache_refresh, "CacheService", return_value=fake_cache),
        patch.object(
            cache_refresh,
            "delete_resource_representations",
            new=AsyncMock(return_value={"durable_deleted": True}),
        ) as mock_delete_representations,
        patch.object(
            cache_refresh,
            "_warm_generated_assets_for_changed_resources",
            new=AsyncMock(return_value={"enabled": True, "resources": 3}),
        ) as mock_warm_assets,
    ):
        stats = await cache_refresh.refresh_cache_for_changed_resources(
            ["resource-1", "resource-2", "resource-1", "resource-3"]
        )

    expected_ids = ["resource-1", "resource-2", "resource-3"]
    expected_tags = [f"resource:{resource_id}" for resource_id in expected_ids]
    assert stats["resource_ids"] == 3
    assert fake_cache.cached_records_calls == [expected_tags]
    assert fake_cache.invalidate_calls == [expected_tags]
    mock_delete_representations.assert_awaited_once_with(
        expected_ids,
        cache_service=fake_cache,
    )
    mock_warm_assets.assert_awaited_once_with(expected_ids)


@pytest.mark.asyncio
async def test_warm_generated_assets_for_changed_resources_warms_all_generated_assets(
    monkeypatch,
):
    resource_dicts = [{"id": "resource-1", "dct_title_s": "Resource 1"}]
    monkeypatch.setenv("BRIDGE_GENERATED_ASSET_REFRESH_ENABLED", "true")

    with (
        patch.object(
            cache_refresh,
            "_fetch_changed_resource_dicts",
            new=AsyncMock(return_value=resource_dicts),
        ) as mock_fetch,
        patch.object(
            cache_refresh,
            "_prime_thumbnail_caches",
            new=AsyncMock(return_value={"attempted": 1, "generated": 1}),
        ) as mock_thumbnails,
        patch.object(
            cache_refresh,
            "_prime_static_map_caches",
            new=AsyncMock(return_value={"attempted": 1, "generated": 1}),
        ) as mock_static_maps,
        patch.object(
            cache_refresh,
            "_prime_resource_class_icon_caches",
            new=AsyncMock(return_value={"attempted": 1, "generated": 1}),
        ) as mock_icons,
    ):
        stats = await cache_refresh._warm_generated_assets_for_changed_resources(["resource-1"])

    assert stats == {
        "enabled": True,
        "resources": 1,
        "thumbnails": {"attempted": 1, "generated": 1},
        "static_maps": {"attempted": 1, "generated": 1},
        "resource_class_icons": {"attempted": 1, "generated": 1},
    }
    mock_fetch.assert_awaited_once_with(["resource-1"])
    mock_thumbnails.assert_awaited_once()
    mock_static_maps.assert_awaited_once()
    mock_icons.assert_awaited_once()


@pytest.mark.asyncio
async def test_bridge_static_map_warm_skips_redis_asset_body_hydration():
    resource_dicts = [{"id": "resource-1", "locn_geometry": "ENVELOPE(-1,1,1,-1)"}]

    with patch(
        "scripts.prime_static_map_cache._prime_static_maps_for_resource",
        new=AsyncMock(return_value=("cached", "resource-1", "ok")),
    ) as mock_prime_static_map:
        stats = await cache_refresh._prime_static_map_caches(
            resource_dicts,
            concurrency=1,
            force=False,
        )

    assert stats == {"attempted": 1, "cached": 1}
    mock_prime_static_map.assert_awaited_once()
    assert mock_prime_static_map.await_args.kwargs["hydrate_assets"] is False


@pytest.mark.asyncio
async def test_warm_generated_assets_can_be_disabled(monkeypatch):
    monkeypatch.setenv("BRIDGE_GENERATED_ASSET_REFRESH_ENABLED", "false")

    with patch.object(
        cache_refresh,
        "_fetch_changed_resource_dicts",
        new=AsyncMock(),
    ) as mock_fetch:
        stats = await cache_refresh._warm_generated_assets_for_changed_resources(["resource-1"])

    assert stats == {"enabled": False}
    mock_fetch.assert_not_awaited()
