from unittest.mock import MagicMock, patch

import scripts.prime_static_map_cache as prime_static_map_cache


def test_prime_static_maps_uses_signature_aware_cache_checks():
    service = MagicMock()
    service.geometry_signature.return_value = "sig-123"
    service.map_exists.return_value = True
    service.basemap_exists.return_value = True

    with patch.object(prime_static_map_cache, "StaticMapService", return_value=service):
        status, detail = prime_static_map_cache._prime_static_maps_sync(
            "resource-1",
            "ENVELOPE(-1, 1, 1, -1)",
            force=False,
        )

    assert (status, detail) == ("cached", "both caches already primed")
    service.map_exists.assert_called_once_with("resource-1", source_signature="sig-123")
    service.basemap_exists.assert_called_once_with("resource-1", source_signature="sig-123")
    service.generate_map.assert_not_called()
    service.generate_basemap.assert_not_called()


def test_prime_static_maps_generates_with_same_signature():
    service = MagicMock()
    service.geometry_signature.return_value = "sig-123"
    service.map_exists.return_value = False
    service.basemap_exists.return_value = False
    service.generate_map.return_value = b"map"
    service.generate_basemap.return_value = b"basemap"

    with patch.object(prime_static_map_cache, "StaticMapService", return_value=service):
        status, detail = prime_static_map_cache._prime_static_maps_sync(
            "resource-1",
            "ENVELOPE(-1, 1, 1, -1)",
            force=False,
        )

    assert (status, detail) == ("generated", "generated=2")
    service.generate_map.assert_called_once_with(
        "resource-1",
        "ENVELOPE(-1, 1, 1, -1)",
        source_signature="sig-123",
    )
    service.generate_basemap.assert_called_once_with(
        "resource-1",
        "ENVELOPE(-1, 1, 1, -1)",
        source_signature="sig-123",
    )
