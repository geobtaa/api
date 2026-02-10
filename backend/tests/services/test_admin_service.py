"""
Tests for the admin service layer.
"""

import json
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.services.admin_service import (
    AdminService,
    CacheManagementError,
    CacheManagementService,
    ReindexingError,
    ReindexingService,
    ResourceNotFoundError,
    ResourceProcessingService,
)


class TestCacheManagementService:
    """Test the cache management service."""

    @pytest.mark.asyncio
    async def test_clear_cache_by_type_search(self):
        """Test clearing search cache."""
        mock_cache_service = Mock()
        mock_cache_service.invalidate_tags = AsyncMock()
        mock_cache_service.flush_all = AsyncMock()
        service = CacheManagementService(mock_cache_service)

        result = await service.clear_cache_by_type("search")

        assert result["message"] == "Cache cleared successfully: search"
        mock_cache_service.invalidate_tags.assert_awaited_once_with(["search"])
        mock_cache_service.flush_all.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_clear_cache_by_type_resource(self):
        """Test clearing resource cache."""
        mock_cache_service = Mock()
        mock_cache_service.invalidate_tags = AsyncMock()
        mock_cache_service.flush_all = AsyncMock()
        service = CacheManagementService(mock_cache_service)

        result = await service.clear_cache_by_type("resource")

        assert result["message"] == "Cache cleared successfully: resource"
        mock_cache_service.invalidate_tags.assert_awaited_once_with(["resource"])
        mock_cache_service.flush_all.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_clear_cache_by_type_suggest(self):
        """Test clearing suggest cache."""
        mock_cache_service = Mock()
        mock_cache_service.invalidate_tags = AsyncMock()
        mock_cache_service.flush_all = AsyncMock()
        service = CacheManagementService(mock_cache_service)

        result = await service.clear_cache_by_type("suggest")

        assert result["message"] == "Cache cleared successfully: suggest"
        mock_cache_service.invalidate_tags.assert_awaited_once_with(["suggest"])
        mock_cache_service.flush_all.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_clear_cache_by_type_all(self):
        """Test clearing all cache."""
        mock_cache_service = Mock()
        mock_cache_service.invalidate_tags = AsyncMock()
        mock_cache_service.flush_all = AsyncMock()
        service = CacheManagementService(mock_cache_service)

        result = await service.clear_cache_by_type("all")

        assert result["message"] == "Cache cleared successfully: all"
        # When cache_type is "all", it should invalidate all types AND flush all.
        # invalidate_tags is called once per tag group (search, resource, suggest, map).
        assert mock_cache_service.invalidate_tags.await_count == 4
        mock_cache_service.invalidate_tags.assert_any_await(["search"])
        mock_cache_service.invalidate_tags.assert_any_await(["resource"])
        mock_cache_service.invalidate_tags.assert_any_await(["suggest"])
        mock_cache_service.invalidate_tags.assert_any_await(["map"])
        mock_cache_service.flush_all.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_clear_cache_by_type_none(self):
        """Test clearing all cache when no type specified."""
        mock_cache_service = Mock()
        mock_cache_service.invalidate_tags = AsyncMock()
        mock_cache_service.flush_all = AsyncMock()
        service = CacheManagementService(mock_cache_service)

        result = await service.clear_cache_by_type(None)

        assert result["message"] == "Cache cleared successfully: all"
        assert mock_cache_service.invalidate_tags.await_count == 4
        mock_cache_service.invalidate_tags.assert_any_await(["search"])
        mock_cache_service.invalidate_tags.assert_any_await(["resource"])
        mock_cache_service.invalidate_tags.assert_any_await(["suggest"])
        mock_cache_service.invalidate_tags.assert_any_await(["map"])
        mock_cache_service.flush_all.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_clear_cache_error(self):
        """Test cache clearing error handling."""
        mock_cache_service = Mock()
        mock_cache_service.invalidate_tags = AsyncMock(side_effect=Exception("Cache error"))
        service = CacheManagementService(mock_cache_service)

        with pytest.raises(CacheManagementError) as exc_info:
            await service.clear_cache_by_type("search")

        assert "Failed to clear cache" in str(exc_info.value)


class TestReindexingService:
    """Test the reindexing service."""

    @pytest.mark.asyncio
    async def test_reindex_all_resources_success(self):
        """Test successful reindexing."""
        service = ReindexingService()

        with (
            patch("app.services.admin_service.ENDPOINT_CACHE", True),
            patch.object(
                ReindexingService,
                "check_spatial_facet_readiness",
                new_callable=AsyncMock,
                return_value={
                    "ready": True,
                    "progress": 100,
                    "indexed_resources": 1000,
                    "total_resources": 1000,
                },
            ),
            patch("app.services.admin_service.CacheService") as mock_cache_cls,
            patch("app.services.admin_service.reindex_resources") as mock_reindex,
        ):
            mock_cache = Mock()
            mock_cache.invalidate_tags = AsyncMock()
            mock_cache_cls.return_value = mock_cache
            mock_reindex.return_value = {"indexed": 100}

            result = await service.reindex_all_resources()

            assert result["status"] == "success"
            assert result["message"] == "Reindexing completed"
            assert result["details"] == {"indexed": 100}
            mock_cache.invalidate_tags.assert_awaited_once_with(["search", "suggest", "map"])
            mock_reindex.assert_called_once()

    @pytest.mark.asyncio
    async def test_reindex_all_resources_no_cache(self):
        """Test reindexing when cache is disabled."""
        service = ReindexingService()

        with (
            patch("app.services.admin_service.ENDPOINT_CACHE", False),
            patch.object(
                ReindexingService,
                "check_spatial_facet_readiness",
                new_callable=AsyncMock,
                return_value={"ready": True},
            ),
            patch("app.services.admin_service.CacheService") as mock_cache_cls,
            patch("app.services.admin_service.reindex_resources") as mock_reindex,
        ):
            mock_reindex.return_value = {"indexed": 50}

            result = await service.reindex_all_resources()

            assert result["status"] == "success"
            assert result["details"] == {"indexed": 50}
            mock_cache_cls.assert_not_called()
            mock_reindex.assert_called_once()

    @pytest.mark.asyncio
    async def test_reindex_all_resources_error(self):
        """Test reindexing error handling."""
        service = ReindexingService()

        with patch("app.services.admin_service.reindex_resources") as mock_reindex:
            mock_reindex.side_effect = Exception("Reindexing failed")

            with pytest.raises(ReindexingError) as exc_info:
                await service.reindex_all_resources()

            assert "Reindexing failed" in str(exc_info.value)


class TestResourceProcessingService:
    """Test the resource processing service."""

    @pytest.fixture
    def mock_resource_data(self):
        """Sample resource data for testing."""
        return {
            "id": "test-resource-1",
            "title": "Test Resource",
            "dc_format_s": "shapefile",
            "dct_references_s": json.dumps(
                {"http://schema.org/downloadUrl": "https://example.com/data.zip"}
            ),
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
        }

    @pytest.mark.asyncio
    async def test_get_resource_by_id_success(self, mock_resource_data):
        """Test successful resource retrieval."""
        service = ResourceProcessingService()

        with patch("app.services.admin_service.database") as mock_db:
            mock_db.transaction.return_value.__aenter__.return_value = mock_db
            # Create a mock that behaves like a database result row
            mock_result = Mock()
            mock_result.__iter__ = Mock(return_value=iter(mock_resource_data.items()))
            mock_result.keys = Mock(return_value=mock_resource_data.keys())
            mock_result.items = Mock(return_value=mock_resource_data.items())
            mock_result.values = Mock(return_value=mock_resource_data.values())
            mock_result.get = Mock(
                side_effect=lambda key, default=None: mock_resource_data.get(key, default)
            )
            mock_result.__getitem__ = Mock(side_effect=lambda key: mock_resource_data[key])
            mock_result.__contains__ = Mock(side_effect=lambda key: key in mock_resource_data)
            mock_db.fetch_one = AsyncMock(return_value=mock_result)

            result = await service.get_resource_by_id("test-resource-1")

            assert result["id"] == "test-resource-1"
            assert result["title"] == "Test Resource"
            # Datetime should be converted to ISO format
            assert isinstance(result["created_at"], str)

    @pytest.mark.asyncio
    async def test_get_resource_by_id_not_found(self):
        """Test resource not found."""
        service = ResourceProcessingService()

        with patch("app.services.admin_service.database") as mock_db:
            mock_db.transaction.return_value.__aenter__.return_value = mock_db
            mock_db.fetch_one = AsyncMock(return_value=None)

            with pytest.raises(ResourceNotFoundError) as exc_info:
                await service.get_resource_by_id("nonexistent")

            assert "Resource nonexistent not found" in str(exc_info.value)

    def test_parse_resource_references_string(self):
        """Test parsing string references."""
        from tests.utils.distribution_helpers import (
            make_distribution_context,
            make_distribution_record,
        )

        service = ResourceProcessingService()
        resource = {"id": "test-id"}
        record = make_distribution_record(
            "test-id", "http://schema.org/downloadUrl", "https://example.com/data.zip"
        )
        ctx = make_distribution_context("test-id", [record])
        result = service.parse_resource_references(resource, "test-id", distribution_context=ctx)
        assert result["http://schema.org/downloadUrl"] == "https://example.com/data.zip"

    def test_parse_resource_references_dict(self):
        """Test parsing dict references."""
        from tests.utils.distribution_helpers import (
            make_distribution_context,
            make_distribution_record,
        )

        service = ResourceProcessingService()
        resource = {"id": "test-id"}
        record = make_distribution_record(
            "test-id", "http://schema.org/downloadUrl", "https://example.com/data.zip"
        )
        ctx = make_distribution_context("test-id", [record])
        result = service.parse_resource_references(resource, "test-id", distribution_context=ctx)
        assert result["http://schema.org/downloadUrl"] == "https://example.com/data.zip"

    def test_parse_resource_references_invalid_json(self):
        """Test parsing invalid JSON references."""
        service = ResourceProcessingService()
        resource = {"dct_references_s": "invalid json"}

        result = service.parse_resource_references(resource, "test-id")

        assert result == {}

    def test_determine_asset_info_string_value(self):
        """Test determining asset info from string reference."""
        service = ResourceProcessingService()
        resource = {"dc_format_s": "shapefile"}
        references = {"http://schema.org/downloadUrl": "https://example.com/data.zip"}

        asset_path, asset_type = service.determine_asset_info(resource, references, "test-id")

        assert asset_path == "https://example.com/data.zip"
        assert asset_type == "download"

    def test_determine_asset_info_array_value(self):
        """Test determining asset info from array reference."""
        service = ResourceProcessingService()
        resource = {"dc_format_s": "shapefile"}
        references = {
            "http://schema.org/downloadUrl": [
                "https://example.com/data1.zip",
                "https://example.com/data2.zip",
            ]
        }

        asset_path, asset_type = service.determine_asset_info(resource, references, "test-id")

        assert asset_path == "https://example.com/data1.zip"
        assert asset_type == "download"

    def test_determine_asset_info_fallback(self):
        """Test determining asset info with format fallback."""
        service = ResourceProcessingService()
        resource = {"dc_format_s": "geotiff"}
        references = {}

        asset_path, asset_type = service.determine_asset_info(resource, references, "test-id")

        assert asset_path is None
        assert asset_type == "geotiff"

    @pytest.mark.asyncio
    async def test_start_summarization_task_success(self, mock_resource_data):
        """Test successful summarization task start."""
        mock_cache_service = Mock()
        mock_cache_service.invalidate_tags = AsyncMock()
        service = ResourceProcessingService(cache_service=mock_cache_service)

        with patch("app.services.admin_service.generate_resource_summary") as mock_task:
            mock_task_instance = Mock()
            mock_task_instance.id = "task-123"
            mock_task.delay.return_value = mock_task_instance

            task_id = await service.start_summarization_task(
                "test-resource-1", mock_resource_data, "https://example.com/data.zip", "download"
            )

            assert task_id == "task-123"
            mock_task.delay.assert_called_once_with(
                resource_id="test-resource-1",
                metadata=mock_resource_data,
                asset_path="https://example.com/data.zip",
                asset_type="download",
            )
            mock_cache_service.invalidate_tags.assert_awaited_once_with(
                ["resource:test-resource-1", "search"]
            )

    @pytest.mark.asyncio
    async def test_start_geo_entities_task_success(self, mock_resource_data):
        """Test successful geo entities task start."""
        mock_cache_service = Mock()
        mock_cache_service.invalidate_tags = AsyncMock()
        service = ResourceProcessingService(cache_service=mock_cache_service)

        with patch("app.services.admin_service.generate_geo_entities") as mock_task:
            mock_task_instance = Mock()
            mock_task_instance.id = "task-456"
            mock_task.delay.return_value = mock_task_instance

            task_id = await service.start_geo_entities_task("test-resource-1", mock_resource_data)

            assert task_id == "task-456"
            mock_task.delay.assert_called_once_with(
                resource_id="test-resource-1", metadata=mock_resource_data
            )
            mock_cache_service.invalidate_tags.assert_awaited_once_with(
                ["resource:test-resource-1", "search"]
            )


class TestAdminService:
    """Test the main admin service."""

    def test_init(self):
        """Test service initialization."""
        cache_service = Mock()
        reindex_service = Mock()
        resource_service = Mock()

        service = AdminService(cache_service, reindex_service, resource_service)

        assert service.cache_management_service == cache_service
        assert service.reindexing_service == reindex_service
        assert service.resource_processing_service == resource_service

    @pytest.mark.asyncio
    async def test_clear_cache(self):
        """Test cache clearing through main service."""
        mock_cache_service = Mock()
        mock_cache_service.clear_cache_by_type = AsyncMock(
            return_value={"message": "Cache cleared"}
        )

        service = AdminService(cache_management_service=mock_cache_service)

        result = await service.clear_cache("search")

        assert result["message"] == "Cache cleared"
        mock_cache_service.clear_cache_by_type.assert_called_once_with("search")

    @pytest.mark.asyncio
    async def test_reindex_resources(self):
        """Test reindexing through main service."""
        mock_reindex_service = Mock()
        mock_reindex_service.reindex_all_resources = AsyncMock(return_value={"status": "success"})

        service = AdminService(reindexing_service=mock_reindex_service)

        result = await service.reindex_resources()

        assert result["status"] == "success"
        mock_reindex_service.reindex_all_resources.assert_called_once()

    @pytest.mark.asyncio
    async def test_summarize_resource(self):
        """Test resource summarization through main service."""
        mock_resource_service = Mock()
        mock_resource_service.get_resource_by_id = AsyncMock(
            return_value={"id": "test", "title": "Test"}
        )
        mock_resource_service.parse_resource_references = Mock(return_value={})
        mock_resource_service.determine_asset_info = Mock(return_value=(None, None))
        mock_resource_service.start_summarization_task = AsyncMock(return_value="task-123")

        service = AdminService(resource_processing_service=mock_resource_service)

        result = await service.summarize_resource("test-resource")

        assert result["status"] == "success"
        assert result["task_id"] == "task-123"
        assert result["message"] == "Summary generation started"

    @pytest.mark.asyncio
    async def test_identify_geo_entities(self):
        """Test geo entity identification through main service."""
        mock_resource_service = Mock()
        mock_resource_service.get_resource_by_id = AsyncMock(
            return_value={"id": "test", "title": "Test"}
        )
        mock_resource_service.start_geo_entities_task = AsyncMock(return_value="task-456")

        service = AdminService(resource_processing_service=mock_resource_service)

        result = await service.identify_geo_entities("test-resource")

        assert result["status"] == "success"
        assert result["task_id"] == "task-456"
        assert result["message"] == "Geographic entity identification started"
