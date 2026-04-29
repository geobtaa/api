from unittest.mock import MagicMock, call, patch

from app.services.static_map_service import StaticMapService


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
        patch("app.services.static_map_service.store_durable_visual_asset_link") as mock_link,
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
