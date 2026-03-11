from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import scripts.prime_thumbnail_cache as prime_thumbnail_cache


@pytest.mark.asyncio
async def test_prime_thumbnail_no_source_records_placeheld():
    resource = {"id": "resource-no-source", "dct_accessrights_s": "Public"}

    with (
        patch.object(prime_thumbnail_cache, "fetch_distribution_context", AsyncMock()),
        patch.object(prime_thumbnail_cache, "safe_record_thumbnail_state", new=AsyncMock()) as mock_state,
        patch.object(prime_thumbnail_cache, "ImageService") as mock_service_cls,
    ):
        service = MagicMock()
        service._get_thumbnail_source_url.return_value = None
        mock_service_cls.return_value = service

        result = await prime_thumbnail_cache._prime_thumbnail_for_resource(resource, force=False)

        assert result == ("skipped-no-source", "resource-no-source", "no thumbnail source")
        payload = mock_state.await_args.args[0]
        assert payload.state == "placeheld"
        assert payload.resource_id == "resource-no-source"


@pytest.mark.asyncio
async def test_prime_thumbnail_cached_remote_records_success():
    resource = {"id": "resource-cached", "dct_accessrights_s": "Public"}
    source_url = "https://example.com/thumb.png"

    with (
        patch.object(prime_thumbnail_cache, "fetch_distribution_context", AsyncMock()),
        patch.object(prime_thumbnail_cache, "safe_record_thumbnail_state", new=AsyncMock()) as mock_state,
        patch.object(prime_thumbnail_cache, "ImageService") as mock_service_cls,
    ):
        service = MagicMock()
        service._get_thumbnail_source_url.return_value = source_url
        service._is_cog_url.return_value = False
        service._is_pmtiles_url.return_value = False
        service._is_manifest_url.return_value = False
        service.get_cached_image = AsyncMock(return_value=b"cached-image")
        mock_service_cls.return_value = service

        with patch.object(
            prime_thumbnail_cache,
            "_compute_thumbnail_image_hash",
            return_value="abc123",
        ):
            result = await prime_thumbnail_cache._prime_thumbnail_for_resource(resource, force=False)

        assert result == ("cached", "resource-cached", "thumbnail already cached")
        payload = mock_state.await_args.args[0]
        assert payload.state == "success"
        assert payload.source_hash == "abc123"
