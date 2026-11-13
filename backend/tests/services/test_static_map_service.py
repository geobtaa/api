from unittest.mock import MagicMock, call, patch

from app.services.static_map_service import StaticMapService
from app.services.visual_asset_cache import cache_visual_asset


def test_get_asset_hash_recovers_alias_from_durable_link():
    asset_hash = "a" * 64
    service = StaticMapService()

    with (
        patch.object(service, "_alias_cache", return_value=None),
        patch.object(service, "get_cached_asset_sync", return_value=b"map-bytes") as mock_get,
        patch.object(service, "set_asset_hash_sync") as mock_set,
        patch(
            "app.services.static_map_service.get_durable_visual_asset_hash_for_resource",
            return_value=asset_hash,
        ) as mock_link,
    ):
        result = service.get_asset_hash_sync(
            "resource-1",
            variant="resource-class-icon",
            source_signature="sig-123",
        )

    assert result == asset_hash
    mock_link.assert_called_once_with(
        "resource-1",
        asset_kind="resource-class-icon",
        source_signature="sig-123",
    )
    mock_get.assert_called_once_with(asset_hash)
    mock_set.assert_called_once_with(
        "resource-1",
        variant="resource-class-icon",
        map_hash=asset_hash,
        source_signature="sig-123",
    )


def test_materialize_asset_persists_resource_link():
    service = StaticMapService()
    service.map_cache = MagicMock()
    map_bytes = b"\x89PNG\r\n\x1a\nmap"

    with (
        patch.object(service, "set_asset_hash_sync") as mock_set_hash,
        patch("app.services.static_map_service.store_durable_visual_asset"),
        patch(
            "app.services.static_map_service.store_durable_visual_asset_link", return_value=True
        ) as mock_link,
    ):
        asset_hash = service.materialize_asset_sync(
            "resource-1",
            variant="resource-class-icon",
            map_bytes=map_bytes,
            source_signature="sig-123",
        )

    assert asset_hash
    mock_link.assert_has_calls(
        [
            call(
                "resource-1",
                asset_hash=asset_hash,
                asset_kind="resource-class-icon",
                source_signature="sig-123",
            ),
            call(
                "resource-1",
                asset_hash=asset_hash,
                asset_kind="resource-class-icon",
                source_signature=None,
            ),
        ]
    )
    mock_set_hash.assert_has_calls(
        [
            call(
                "resource-1",
                variant="resource-class-icon",
                map_hash=asset_hash,
                source_signature="sig-123",
            ),
            call(
                "resource-1",
                variant="resource-class-icon",
                map_hash=asset_hash,
                source_signature=None,
            ),
        ]
    )


def test_materialize_asset_can_skip_redis_asset_body_hydration():
    service = StaticMapService()
    service.map_cache = MagicMock()
    map_bytes = b"\x89PNG\r\n\x1a\nmap"

    with (
        patch.object(service, "cache_asset_sync") as mock_cache_asset,
        patch.object(service, "set_asset_hash_sync"),
        patch("app.services.static_map_service.store_durable_visual_asset"),
        patch("app.services.static_map_service.store_durable_visual_asset_link"),
    ):
        asset_hash = service.materialize_asset_sync(
            "resource-1",
            variant="static_map_v7",
            map_bytes=map_bytes,
            source_signature="sig-123",
            hydrate_asset=False,
        )

    assert asset_hash
    mock_cache_asset.assert_not_called()


def test_materialize_cached_variant_preserves_no_hydration_for_legacy_bytes():
    service = StaticMapService()
    service.map_cache = MagicMock()
    service.map_cache.get.return_value = b"\x89PNG\r\n\x1a\nlegacy-map"

    with (
        patch.object(service, "get_asset_hash_sync", return_value=None),
        patch.object(service, "materialize_asset_sync", return_value="c" * 64) as mock_materialize,
    ):
        asset_hash = service.materialize_cached_variant_sync(
            "resource-1",
            variant="static_map_v7",
            source_signature="sig-123",
            hydrate_asset=False,
        )

    assert asset_hash == "c" * 64
    mock_materialize.assert_called_once_with(
        "resource-1",
        variant="static_map_v7",
        map_bytes=b"\x89PNG\r\n\x1a\nlegacy-map",
        source_signature="sig-123",
        hydrate_asset=False,
    )


def test_get_cached_asset_waits_through_redis_loading(monkeypatch):
    service = StaticMapService()
    map_hash = "b" * 64

    class LoadingOnceCache:
        calls = 0

        def get(self, _key):
            self.calls += 1
            if self.calls == 1:
                raise Exception("Redis is loading the dataset in memory")
            return b"map-bytes"

    service.map_cache = LoadingOnceCache()
    monkeypatch.setenv("VISUAL_ASSET_REDIS_LOADING_MAX_WAIT_SECONDS", "1")
    monkeypatch.setenv("VISUAL_ASSET_REDIS_LOADING_RETRY_SECONDS", "0.05")

    with patch("app.services.visual_asset_cache.time.sleep") as mock_sleep:
        result = service.get_cached_asset_sync(map_hash)

    assert result == b"map-bytes"
    mock_sleep.assert_called_once()


def test_cache_visual_asset_waits_through_redis_loading(monkeypatch):
    class LoadingOnceCache:
        calls = 0

        def set(self, _key, _value):
            self.calls += 1
            if self.calls == 1:
                raise Exception("Redis is loading the dataset in memory")
            return True

    cache = LoadingOnceCache()
    monkeypatch.setenv("VISUAL_ASSET_REDIS_LOADING_MAX_WAIT_SECONDS", "1")
    monkeypatch.setenv("VISUAL_ASSET_REDIS_LOADING_RETRY_SECONDS", "0.05")

    with patch("app.services.visual_asset_cache.time.sleep") as mock_sleep:
        assert cache_visual_asset(cache, "asset-key", b"asset-bytes") is True

    assert cache.calls == 2
    mock_sleep.assert_called_once()
