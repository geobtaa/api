"""
Unit tests for SpatialFacetService
"""
import pytest
from unittest.mock import AsyncMock, patch

from app.services.spatial_facet_service import SpatialFacetService


class TestSpatialFacetService:
    """Test cases for SpatialFacetService class."""

    def test_spatial_facet_service_initialization(self):
        """Test that the SpatialFacetService can be initialized."""
        resource_dict = {
            "id": "test-resource",
            "dcat_bbox": "ENVELOPE(-123.0, -122.0, 45.0, 44.0)"
        }
        service = SpatialFacetService(resource_dict)
        assert service is not None
        assert service.resource_dict == resource_dict

    def test_parse_bbox_to_geometry_valid_envelope(self):
        """Test parsing a valid ENVELOPE string."""
        resource_dict = {"id": "test"}
        service = SpatialFacetService(resource_dict)
        
        bbox = "ENVELOPE(-123.08286, -121.912937, 45.918689, 45.255769)"
        result = service._parse_bbox_to_geometry(bbox)
        
        assert result == (-123.08286, 45.255769, -121.912937, 45.918689)

    def test_parse_bbox_to_geometry_invalid_format(self):
        """Test parsing an invalid bbox format."""
        resource_dict = {"id": "test"}
        service = SpatialFacetService(resource_dict)
        
        bbox = "INVALID_FORMAT"
        result = service._parse_bbox_to_geometry(bbox)
        
        assert result is None

    def test_parse_bbox_to_geometry_empty_string(self):
        """Test parsing an empty bbox string."""
        resource_dict = {"id": "test"}
        service = SpatialFacetService(resource_dict)
        
        bbox = ""
        result = service._parse_bbox_to_geometry(bbox)
        
        assert result is None

    @pytest.mark.asyncio
    async def test_get_spatial_facets_no_bbox(self):
        """Test get_spatial_facets when no bbox is present."""
        resource_dict = {"id": "test-resource"}
        service = SpatialFacetService(resource_dict)
        
        facets = await service.get_spatial_facets()
        
        assert facets == {}

    @pytest.mark.asyncio
    async def test_get_spatial_facets_invalid_bbox(self):
        """Test get_spatial_facets with invalid bbox format."""
        resource_dict = {
            "id": "test-resource",
            "dcat_bbox": "INVALID_FORMAT"
        }
        service = SpatialFacetService(resource_dict)
        
        facets = await service.get_spatial_facets()
        
        assert facets == {}

    @pytest.mark.asyncio
    async def test_get_spatial_facets_with_mock_database(self):
        """Test get_spatial_facets with mocked database responses."""
        resource_dict = {
            "id": "test-resource",
            "dcat_bbox": "ENVELOPE(-123.0, -122.0, 45.0, 44.0)"
        }
        service = SpatialFacetService(resource_dict)
        
        # Mock database responses with required WOF fields
        mock_country = {"name": "United States", "wok_id": 85633793, "parent_id": 0}
        mock_regions = [{"name": "Oregon", "wok_id": 85688517, "parent_id": 85633793}]
        mock_counties = [
            {"county_name": "Multnomah", "county_wok_id": 102081631, "state_wok_id": 85688517, "state_abbrev": "OR"},
            {"county_name": "Washington", "county_wok_id": 102081632, "state_wok_id": 85688517, "state_abbrev": "OR"}
        ]
        
        with patch("app.services.spatial_facet_service.database") as mock_db:
            # Create async mock objects
            mock_db.fetch_one = AsyncMock(return_value=mock_country)
            mock_db.fetch_all = AsyncMock(side_effect=[mock_regions, mock_counties])
            
            facets = await service.get_spatial_facets()
            
            assert "geo.country" in facets
            assert facets["geo.country"] == "United States"
            assert "geo.region" in facets
            assert facets["geo.region"] == ["Oregon"]
            assert "geo.county" in facets
            assert facets["geo.county"] == ["OR|Multnomah", "OR|Washington"]

    @pytest.mark.asyncio
    async def test_get_spatial_facets_database_error(self):
        """Test get_spatial_facets when database throws an error."""
        resource_dict = {
            "id": "test-resource",
            "dcat_bbox": "ENVELOPE(-123.0, -122.0, 45.0, 44.0)"
        }
        service = SpatialFacetService(resource_dict)
        
        with patch("app.services.spatial_facet_service.database") as mock_db:
            mock_db.fetch_one = AsyncMock(side_effect=Exception("Database error"))
            
            facets = await service.get_spatial_facets()
            
            # Should return empty dict on error
            assert facets == {}

    @pytest.mark.asyncio
    async def test_get_resource_spatial_facets_static_method(self):
        """Test the static get_resource_spatial_facets method."""
        resource_id = "test-resource"
        mock_resource = {"id": resource_id, "dcat_bbox": "ENVELOPE(-123.0, -122.0, 45.0, 44.0)"}
        mock_facets = {"geo.country": "United States", "geo.region": ["Oregon"]}
        
        with patch("app.services.spatial_facet_service.database") as mock_db:
            mock_db.fetch_one = AsyncMock(return_value=mock_resource)
            
            # Mock the service instance methods
            with patch.object(SpatialFacetService, 'get_spatial_facets', return_value=mock_facets):
                result = await SpatialFacetService.get_resource_spatial_facets(resource_id)
                
                assert result == mock_facets
                mock_db.fetch_one.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_resource_spatial_facets_resource_not_found(self):
        """Test get_resource_spatial_facets when resource is not found."""
        resource_id = "nonexistent-resource"
        
        with patch("app.services.spatial_facet_service.database") as mock_db:
            mock_db.fetch_one = AsyncMock(return_value=None)
            
            result = await SpatialFacetService.get_resource_spatial_facets(resource_id)
            
            assert result == {}

    @pytest.mark.asyncio
    async def test_batch_get_spatial_facets(self):
        """Test the batch_get_spatial_facets static method."""
        resource_ids = ["resource1", "resource2"]
        mock_resources = [
            {"id": "resource1", "dcat_bbox": "ENVELOPE(-123.0, -122.0, 45.0, 44.0)"},
            {"id": "resource2", "dcat_bbox": "ENVELOPE(-124.0, -123.0, 46.0, 45.0)"}
        ]
        mock_facets1 = {"geo.country": "United States", "geo.region": ["Oregon"]}
        mock_facets2 = {"geo.country": "United States", "geo.region": ["Washington"]}
        
        with patch("app.services.spatial_facet_service.database") as mock_db:
            mock_db.fetch_all = AsyncMock(return_value=mock_resources)
            
            # Mock the service instance methods
            with patch.object(SpatialFacetService, 'get_spatial_facets', side_effect=[mock_facets1, mock_facets2]):
                result = await SpatialFacetService.batch_get_spatial_facets(resource_ids)
                
                assert len(result) == 2
                assert result["resource1"] == mock_facets1
                assert result["resource2"] == mock_facets2

    @pytest.mark.asyncio
    async def test_batch_get_spatial_facets_empty_list(self):
        """Test batch_get_spatial_facets with empty resource list."""
        result = await SpatialFacetService.batch_get_spatial_facets([])
        assert result == {}

    @pytest.mark.asyncio
    async def test_batch_get_spatial_facets_database_error(self):
        """Test batch_get_spatial_facets when database throws an error."""
        resource_ids = ["resource1"]
        
        with patch("app.services.spatial_facet_service.database") as mock_db:
            mock_db.fetch_all = AsyncMock(side_effect=Exception("Database error"))
            
            result = await SpatialFacetService.batch_get_spatial_facets(resource_ids)
            
            assert result == {}
