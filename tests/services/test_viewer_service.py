"""
Tests for the ViewerService.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from app.services.viewer_service import ViewerService, create_viewer_attributes, parse_references


class TestParseReferences:
    """Test cases for parse_references function."""

    def test_parse_references_with_dict_and_valid_json_string(self):
        """Test parsing references from dict with valid JSON string."""
        document = {
            "dct_references_s": '{"iiif": "http://example.com/iiif", "download": "http://example.com/download"}',
            "locn_geometry": "POINT(-93.2650 44.9778)"
        }
        
        result = parse_references(document)
        
        assert isinstance(result, dict)
        assert result["iiif"] == "http://example.com/iiif"
        assert result["download"] == "http://example.com/download"
        assert result["locn_geometry"] == "POINT(-93.2650 44.9778)"

    def test_parse_references_with_dict_and_invalid_json_string(self):
        """Test parsing references from dict with invalid JSON string."""
        document = {
            "dct_references_s": "invalid json{",
            "locn_geometry": "POINT(-93.2650 44.9778)"
        }
        
        result = parse_references(document)
        
        assert isinstance(result, dict)
        assert result == {"locn_geometry": "POINT(-93.2650 44.9778)"}

    def test_parse_references_with_dict_and_dict_references(self):
        """Test parsing references from dict with dict references."""
        document = {
            "dct_references_s": {"iiif": "http://example.com/iiif", "download": "http://example.com/download"},
            "locn_geometry": "POINT(-93.2650 44.9778)"
        }
        
        result = parse_references(document)
        
        assert isinstance(result, dict)
        assert result["iiif"] == "http://example.com/iiif"
        assert result["download"] == "http://example.com/download"
        assert result["locn_geometry"] == "POINT(-93.2650 44.9778)"

    def test_parse_references_with_dict_and_non_dict_references(self):
        """Test parsing references from dict with non-dict references."""
        document = {
            "dct_references_s": ["invalid", "list"],
            "locn_geometry": "POINT(-93.2650 44.9778)"
        }
        
        result = parse_references(document)
        
        assert isinstance(result, dict)
        assert result == {"locn_geometry": "POINT(-93.2650 44.9778)"}

    def test_parse_references_with_dict_and_no_references(self):
        """Test parsing references from dict with no references."""
        document = {
            "locn_geometry": "POINT(-93.2650 44.9778)"
        }
        
        result = parse_references(document)
        
        assert isinstance(result, dict)
        assert result == {"locn_geometry": "POINT(-93.2650 44.9778)"}

    def test_parse_references_with_dict_and_no_geometry(self):
        """Test parsing references from dict with no geometry."""
        document = {
            "dct_references_s": '{"iiif": "http://example.com/iiif"}'
        }
        
        result = parse_references(document)
        
        assert isinstance(result, dict)
        assert result["iiif"] == "http://example.com/iiif"
        assert "locn_geometry" not in result

    def test_parse_references_with_object_with_getitem(self):
        """Test parsing references from object with __getitem__ method."""
        class MockDocument:
            def __init__(self, data):
                self.data = data
            
            def __getitem__(self, key):
                return self.data[key]
            
            def get(self, key, default=None):
                return self.data.get(key, default)
        
        document = MockDocument({
            "dct_references_s": '{"iiif": "http://example.com/iiif"}',
            "locn_geometry": "POINT(-93.2650 44.9778)"
        })
        
        result = parse_references(document)
        
        assert isinstance(result, dict)
        assert result["iiif"] == "http://example.com/iiif"
        assert result["locn_geometry"] == "POINT(-93.2650 44.9778)"

    def test_parse_references_with_object_without_getitem(self):
        """Test parsing references from object without __getitem__ method."""
        class MockDocument:
            def __init__(self, data):
                self.dct_references_s = data.get("dct_references_s", {})
                self.locn_geometry = data.get("locn_geometry")
        
        document = MockDocument({
            "dct_references_s": '{"iiif": "http://example.com/iiif"}',
            "locn_geometry": "POINT(-93.2650 44.9778)"
        })
        
        result = parse_references(document)
        
        assert isinstance(result, dict)
        assert result["iiif"] == "http://example.com/iiif"
        assert result["locn_geometry"] == "POINT(-93.2650 44.9778)"

    def test_parse_references_with_object_geometry_attribute(self):
        """Test parsing references from object with locn_geometry attribute."""
        class MockDocument:
            def __init__(self, data):
                self.dct_references_s = data.get("dct_references_s", {})
                self.locn_geometry = data.get("locn_geometry")
        
        document = MockDocument({
            "dct_references_s": '{"iiif": "http://example.com/iiif"}',
            "locn_geometry": "POINT(-93.2650 44.9778)"
        })
        
        result = parse_references(document)
        
        assert isinstance(result, dict)
        assert result["iiif"] == "http://example.com/iiif"
        assert result["locn_geometry"] == "POINT(-93.2650 44.9778)"

    def test_parse_references_with_object_geometry_method(self):
        """Test parsing references from object with locn_geometry method."""
        class MockDocument:
            def __init__(self, data):
                self.dct_references_s = data.get("dct_references_s", {})
                self._locn_geometry = data.get("locn_geometry")
            
            def get(self, key, default=None):
                if key == "locn_geometry":
                    return self._locn_geometry
                return default
        
        document = MockDocument({
            "dct_references_s": '{"iiif": "http://example.com/iiif"}',
            "locn_geometry": "POINT(-93.2650 44.9778)"
        })
        
        result = parse_references(document)
        
        assert isinstance(result, dict)
        assert result["iiif"] == "http://example.com/iiif"
        assert result["locn_geometry"] == "POINT(-93.2650 44.9778)"

    def test_parse_references_error_handling(self):
        """Test parse_references error handling."""
        # Create a document that will cause an error
        class ErrorDocument:
            def get(self, key, default=None):
                raise Exception("Test error")
        
        document = ErrorDocument()
        
        result = parse_references(document)
        
        assert isinstance(result, dict)
        assert result == {}


class TestCreateViewerAttributes:
    """Test cases for create_viewer_attributes function."""

    @patch('app.services.viewer_service.ItemViewer')
    def test_create_viewer_attributes_with_dict(self, mock_item_viewer):
        """Test creating viewer attributes with dict document."""
        # Mock the ItemViewer
        mock_viewer = MagicMock()
        mock_viewer.viewer_protocol.return_value = "iiif"
        mock_viewer.viewer_endpoint.return_value = "http://example.com/viewer"
        mock_viewer.viewer_geometry.return_value = {"type": "Point", "coordinates": [-93.2650, 44.9778]}
        mock_item_viewer.return_value = mock_viewer
        
        document = {
            "dct_references_s": '{"iiif": "http://example.com/iiif"}',
            "locn_geometry": "POINT(-93.2650 44.9778)"
        }
        
        result = create_viewer_attributes(document)
        
        assert isinstance(result, dict)
        assert result["ui_viewer_protocol"] == "iiif"
        assert result["ui_viewer_endpoint"] == "http://example.com/viewer"
        assert result["ui_viewer_geometry"]["type"] == "Point"
        assert result["ui_viewer_geometry"]["coordinates"] == [-93.2650, 44.9778]
        
        # Verify ItemViewer was called with parsed references
        mock_item_viewer.assert_called_once()
        call_args = mock_item_viewer.call_args[0][0]
        assert call_args["iiif"] == "http://example.com/iiif"
        assert call_args["locn_geometry"] == "POINT(-93.2650 44.9778)"

    @patch('app.services.viewer_service.ItemViewer')
    def test_create_viewer_attributes_with_object(self, mock_item_viewer):
        """Test creating viewer attributes with object document."""
        # Mock the ItemViewer
        mock_viewer = MagicMock()
        mock_viewer.viewer_protocol.return_value = "iiif"
        mock_viewer.viewer_endpoint.return_value = "http://example.com/viewer"
        mock_viewer.viewer_geometry.return_value = {"type": "Point", "coordinates": [-93.2650, 44.9778]}
        mock_item_viewer.return_value = mock_viewer
        
        # Create a mock object that can be converted to dict
        class MockDocument:
            def __init__(self, data):
                self.data = data
            
            def __iter__(self):
                return iter(self.data.items())
        
        document = MockDocument({
            "dct_references_s": '{"iiif": "http://example.com/iiif"}',
            "locn_geometry": "POINT(-93.2650 44.9778)"
        })
        
        result = create_viewer_attributes(document)
        
        assert isinstance(result, dict)
        assert result["ui_viewer_protocol"] == "iiif"
        assert result["ui_viewer_endpoint"] == "http://example.com/viewer"
        assert result["ui_viewer_geometry"]["type"] == "Point"

    @patch('app.services.viewer_service.ItemViewer')
    def test_create_viewer_attributes_geometry_error(self, mock_item_viewer):
        """Test creating viewer attributes when geometry retrieval fails."""
        # Mock the ItemViewer
        mock_viewer = MagicMock()
        mock_viewer.viewer_protocol.return_value = "iiif"
        mock_viewer.viewer_endpoint.return_value = "http://example.com/viewer"
        mock_viewer.viewer_geometry.side_effect = Exception("Geometry error")
        mock_item_viewer.return_value = mock_viewer
        
        document = {
            "dct_references_s": '{"iiif": "http://example.com/iiif"}'
        }
        
        result = create_viewer_attributes(document)
        
        assert isinstance(result, dict)
        assert result["ui_viewer_protocol"] == "iiif"
        assert result["ui_viewer_endpoint"] == "http://example.com/viewer"
        assert result["ui_viewer_geometry"] is None


class TestViewerService:
    """Test cases for ViewerService class."""

    def test_viewer_service_initialization_with_dict(self):
        """Test ViewerService initialization with dict document."""
        document = {
            "dct_references_s": '{"iiif": "http://example.com/iiif"}',
            "locn_geometry": "POINT(-93.2650 44.9778)"
        }
        
        service = ViewerService(document)
        
        assert service.document == document
        assert isinstance(service.references, dict)
        assert service.references["iiif"] == "http://example.com/iiif"
        assert service.references["locn_geometry"] == "POINT(-93.2650 44.9778)"
        assert service.viewer is not None

    def test_viewer_service_initialization_with_object(self):
        """Test ViewerService initialization with object document."""
        class MockDocument:
            def __init__(self, data):
                self.dct_references_s = data.get("dct_references_s", {})
                self.locn_geometry = data.get("locn_geometry")
        
        document = MockDocument({
            "dct_references_s": '{"iiif": "http://example.com/iiif"}',
            "locn_geometry": "POINT(-93.2650 44.9778)"
        })
        
        service = ViewerService(document)
        
        assert service.document == document
        assert isinstance(service.references, dict)
        assert service.references["iiif"] == "http://example.com/iiif"
        assert service.references["locn_geometry"] == "POINT(-93.2650 44.9778)"
        assert service.viewer is not None

    def test_get_viewer_attributes_success(self):
        """Test successful get_viewer_attributes."""
        document = {
            "dct_references_s": '{"iiif": "http://example.com/iiif"}',
            "locn_geometry": "POINT(-93.2650 44.9778)"
        }
        
        service = ViewerService(document)
        
        # Mock the viewer methods
        service.viewer.viewer_protocol = MagicMock(return_value="iiif")
        service.viewer.viewer_endpoint = MagicMock(return_value="http://example.com/viewer")
        service.viewer.viewer_geometry = MagicMock(return_value={"type": "Point", "coordinates": [-93.2650, 44.9778]})
        
        result = service.get_viewer_attributes()
        
        assert isinstance(result, dict)
        assert result["ui_viewer_protocol"] == "iiif"
        assert result["ui_viewer_endpoint"] == "http://example.com/viewer"
        assert result["ui_viewer_geometry"]["type"] == "Point"
        assert result["ui_viewer_geometry"]["coordinates"] == [-93.2650, 44.9778]

    def test_get_viewer_attributes_geometry_error(self):
        """Test get_viewer_attributes when geometry retrieval fails."""
        document = {
            "dct_references_s": '{"iiif": "http://example.com/iiif"}'
        }
        
        service = ViewerService(document)
        
        # Mock the viewer methods
        service.viewer.viewer_protocol = MagicMock(return_value="iiif")
        service.viewer.viewer_endpoint = MagicMock(return_value="http://example.com/viewer")
        service.viewer.viewer_geometry = MagicMock(side_effect=Exception("Geometry error"))
        
        result = service.get_viewer_attributes()
        
        assert isinstance(result, dict)
        assert result["ui_viewer_protocol"] == "iiif"
        assert result["ui_viewer_endpoint"] == "http://example.com/viewer"
        assert result["ui_viewer_geometry"] is None

    def test_get_viewer_attributes_various_protocols(self):
        """Test get_viewer_attributes with various viewer protocols."""
        document = {
            "dct_references_s": '{"iiif": "http://example.com/iiif"}'
        }
        
        service = ViewerService(document)
        
        # Test different protocols
        protocols = ["iiif", "tile", "wms", "wmts", "arcgis"]
        
        for protocol in protocols:
            service.viewer.viewer_protocol = MagicMock(return_value=protocol)
            service.viewer.viewer_endpoint = MagicMock(return_value=f"http://example.com/{protocol}")
            service.viewer.viewer_geometry = MagicMock(return_value=None)
            
            result = service.get_viewer_attributes()
            
            assert result["ui_viewer_protocol"] == protocol
            assert result["ui_viewer_endpoint"] == f"http://example.com/{protocol}"
            assert result["ui_viewer_geometry"] is None

    def test_get_viewer_attributes_with_complex_geometry(self):
        """Test get_viewer_attributes with complex geometry."""
        document = {
            "dct_references_s": '{"iiif": "http://example.com/iiif"}',
            "locn_geometry": "POLYGON((-93.3 44.9, -93.2 44.9, -93.2 45.0, -93.3 45.0, -93.3 44.9))"
        }
        
        service = ViewerService(document)
        
        # Mock complex geometry
        complex_geometry = {
            "type": "Polygon",
            "coordinates": [[[-93.3, 44.9], [-93.2, 44.9], [-93.2, 45.0], [-93.3, 45.0], [-93.3, 44.9]]]
        }
        
        service.viewer.viewer_protocol = MagicMock(return_value="iiif")
        service.viewer.viewer_endpoint = MagicMock(return_value="http://example.com/iiif")
        service.viewer.viewer_geometry = MagicMock(return_value=complex_geometry)
        
        result = service.get_viewer_attributes()
        
        assert result["ui_viewer_geometry"]["type"] == "Polygon"
        assert len(result["ui_viewer_geometry"]["coordinates"]) == 1
        assert len(result["ui_viewer_geometry"]["coordinates"][0]) == 5

    def test_get_viewer_attributes_with_empty_references(self):
        """Test get_viewer_attributes with empty references."""
        document = {}
        
        service = ViewerService(document)
        
        service.viewer.viewer_protocol = MagicMock(return_value=None)
        service.viewer.viewer_endpoint = MagicMock(return_value=None)
        service.viewer.viewer_geometry = MagicMock(return_value=None)
        
        result = service.get_viewer_attributes()
        
        assert isinstance(result, dict)
        assert result["ui_viewer_protocol"] is None
        assert result["ui_viewer_endpoint"] is None
        assert result["ui_viewer_geometry"] is None

    def test_get_viewer_attributes_with_mixed_references(self):
        """Test get_viewer_attributes with mixed reference types."""
        document = {
            "dct_references_s": '{"iiif": "http://example.com/iiif", "tile": "http://example.com/tile", "download": "http://example.com/download"}',
            "locn_geometry": "POINT(-93.2650 44.9778)"
        }
        
        service = ViewerService(document)
        
        service.viewer.viewer_protocol = MagicMock(return_value="iiif")
        service.viewer.viewer_endpoint = MagicMock(return_value="http://example.com/iiif")
        service.viewer.viewer_geometry = MagicMock(return_value={"type": "Point", "coordinates": [-93.2650, 44.9778]})
        
        result = service.get_viewer_attributes()
        
        assert result["ui_viewer_protocol"] == "iiif"
        assert result["ui_viewer_endpoint"] == "http://example.com/iiif"
        assert result["ui_viewer_geometry"]["type"] == "Point"

    def test_viewer_service_with_invalid_json_references(self):
        """Test ViewerService with invalid JSON references."""
        document = {
            "dct_references_s": "invalid json{",
            "locn_geometry": "POINT(-93.2650 44.9778)"
        }
        
        service = ViewerService(document)
        
        # Should still work with empty references
        assert isinstance(service.references, dict)
        assert service.references["locn_geometry"] == "POINT(-93.2650 44.9778)"
        assert len(service.references) == 1  # Only geometry should be present

    def test_viewer_service_with_none_references(self):
        """Test ViewerService with None references."""
        document = {
            "dct_references_s": None,
            "locn_geometry": "POINT(-93.2650 44.9778)"
        }
        
        service = ViewerService(document)
        
        assert isinstance(service.references, dict)
        assert service.references["locn_geometry"] == "POINT(-93.2650 44.9778)"
        assert len(service.references) == 1  # Only geometry should be present

    def test_viewer_service_with_list_references(self):
        """Test ViewerService with list references (invalid type)."""
        document = {
            "dct_references_s": ["invalid", "list"],
            "locn_geometry": "POINT(-93.2650 44.9778)"
        }
        
        service = ViewerService(document)
        
        assert isinstance(service.references, dict)
        assert service.references["locn_geometry"] == "POINT(-93.2650 44.9778)"
        assert len(service.references) == 1  # Only geometry should be present

    def test_viewer_service_without_geometry(self):
        """Test ViewerService without geometry."""
        document = {
            "dct_references_s": '{"iiif": "http://example.com/iiif"}'
        }
        
        service = ViewerService(document)
        
        assert isinstance(service.references, dict)
        assert service.references["iiif"] == "http://example.com/iiif"
        assert "locn_geometry" not in service.references
