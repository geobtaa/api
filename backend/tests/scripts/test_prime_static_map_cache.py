from unittest.mock import MagicMock, patch

import pytest

import scripts.prime_static_map_cache as prime_static_map_cache


def test_prime_static_maps_reuses_signature_aware_durable_cache():
    service = MagicMock()
    service.geometry_signature.return_value = "sig-123"
    service.geometry_variant.return_value = "static_map_v7"
    service.basemap_variant.return_value = "static_basemap_v5"
    service.materialize_cached_variant_sync.side_effect = ["hash-map", "hash-basemap"]

    with patch.object(prime_static_map_cache, "StaticMapService", return_value=service):
        status, detail = prime_static_map_cache._prime_static_maps_sync(
            "resource-1",
            "ENVELOPE(-1, 1, 1, -1)",
            force=False,
        )

    assert (status, detail) == ("cached", "both caches already primed")
    assert service.materialize_cached_variant_sync.call_args_list == [
        (
            ("resource-1",),
            {
                "variant": "static_map_v7",
                "source_signature": "sig-123",
                "hydrate_asset": True,
            },
        ),
        (
            ("resource-1",),
            {
                "variant": "static_basemap_v5",
                "source_signature": "sig-123",
                "hydrate_asset": True,
            },
        ),
    ]
    service.generate_map.assert_not_called()
    service.generate_basemap.assert_not_called()


def test_prime_static_maps_generates_with_same_signature():
    service = MagicMock()
    service.geometry_signature.return_value = "sig-123"
    service.geometry_variant.return_value = "static_map_v7"
    service.basemap_variant.return_value = "static_basemap_v5"
    service.materialize_cached_variant_sync.side_effect = [None, None]
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
        hydrate_asset=True,
    )
    service.generate_basemap.assert_called_once_with(
        "resource-1",
        "ENVELOPE(-1, 1, 1, -1)",
        source_signature="sig-123",
        hydrate_asset=True,
    )


def test_prime_static_maps_can_skip_redis_asset_hydration():
    service = MagicMock()
    service.geometry_signature.return_value = "sig-123"
    service.geometry_variant.return_value = "static_map_v7"
    service.basemap_variant.return_value = "static_basemap_v5"
    service.materialize_cached_variant_sync.side_effect = ["hash-map", "hash-basemap"]

    with patch.object(prime_static_map_cache, "StaticMapService", return_value=service):
        status, detail = prime_static_map_cache._prime_static_maps_sync(
            "resource-1",
            "ENVELOPE(-1, 1, 1, -1)",
            force=False,
            hydrate_assets=False,
        )

    assert (status, detail) == ("cached", "both caches already primed")
    assert service.materialize_cached_variant_sync.call_args_list == [
        (
            ("resource-1",),
            {
                "variant": "static_map_v7",
                "source_signature": "sig-123",
                "hydrate_asset": False,
            },
        ),
        (
            ("resource-1",),
            {
                "variant": "static_basemap_v5",
                "source_signature": "sig-123",
                "hydrate_asset": False,
            },
        ),
    ]


def test_prime_static_maps_generates_without_redis_asset_hydration_when_disabled():
    service = MagicMock()
    service.geometry_signature.return_value = "sig-123"
    service.geometry_variant.return_value = "static_map_v7"
    service.basemap_variant.return_value = "static_basemap_v5"
    service.materialize_cached_variant_sync.side_effect = [None, None]
    service.generate_map.return_value = b"map"
    service.generate_basemap.return_value = b"basemap"

    with patch.object(prime_static_map_cache, "StaticMapService", return_value=service):
        status, detail = prime_static_map_cache._prime_static_maps_sync(
            "resource-1",
            "ENVELOPE(-1, 1, 1, -1)",
            force=False,
            hydrate_assets=False,
        )

    assert (status, detail) == ("generated", "generated=2")
    service.generate_map.assert_called_once_with(
        "resource-1",
        "ENVELOPE(-1, 1, 1, -1)",
        source_signature="sig-123",
        hydrate_asset=False,
    )
    service.generate_basemap.assert_called_once_with(
        "resource-1",
        "ENVELOPE(-1, 1, 1, -1)",
        source_signature="sig-123",
        hydrate_asset=False,
    )


@pytest.mark.asyncio
async def test_run_refuses_full_corpus_redis_asset_hydration():
    args = prime_static_map_cache.argparse.Namespace(
        resource_ids=[],
        limit=None,
        hydrate_assets=True,
        allow_full_hydration=False,
        batch_size=100,
        concurrency=2,
        force=False,
        strict_failures=False,
    )

    with patch.object(prime_static_map_cache, "_count_resources", return_value=1000):
        assert await prime_static_map_cache._run(args) == 2
