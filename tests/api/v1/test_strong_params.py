"""
Tests for the strong_params module.
"""

import pytest

from app.api.v1.strong_params import (
    SEARCH_ALLOWED_PARAMS,
    GAZETTEER_ALLOWED_PARAMS,
    RESOURCE_ALLOWED_PARAMS,
    ADMIN_ALLOWED_PARAMS,
    MCP_ALLOWED_PARAMS,
    SHAPEFILE_ALLOWED_PARAMS,
    THUMBNAIL_ALLOWED_PARAMS,
)


class TestStrongParams:
    """Test cases for strong_params module."""

    def test_search_allowed_params_structure(self):
        """Test that SEARCH_ALLOWED_PARAMS contains expected parameters."""
        assert isinstance(SEARCH_ALLOWED_PARAMS, list)
        assert len(SEARCH_ALLOWED_PARAMS) > 0
        
        # Check core search parameters
        assert "q" in SEARCH_ALLOWED_PARAMS
        assert "page" in SEARCH_ALLOWED_PARAMS
        assert "per_page" in SEARCH_ALLOWED_PARAMS
        assert "sort" in SEARCH_ALLOWED_PARAMS
        assert "callback" in SEARCH_ALLOWED_PARAMS

    def test_search_allowed_params_facet_filters(self):
        """Test that SEARCH_ALLOWED_PARAMS contains facet filter parameters."""
        # Check facet filter parameters
        assert "fq[resource_class_agg][]" in SEARCH_ALLOWED_PARAMS
        assert "fq[resource_type_agg][]" in SEARCH_ALLOWED_PARAMS
        assert "fq[spatial_agg][]" in SEARCH_ALLOWED_PARAMS
        assert "fq[issued_agg][]" in SEARCH_ALLOWED_PARAMS
        assert "fq[index_year_agg][]" in SEARCH_ALLOWED_PARAMS
        assert "fq[language_agg][]" in SEARCH_ALLOWED_PARAMS
        assert "fq[creator_agg][]" in SEARCH_ALLOWED_PARAMS
        assert "fq[provider_agg][]" in SEARCH_ALLOWED_PARAMS
        assert "fq[access_rights_agg][]" in SEARCH_ALLOWED_PARAMS
        assert "fq[georeferenced_agg][]" in SEARCH_ALLOWED_PARAMS
        assert "fq[id_agg][]" in SEARCH_ALLOWED_PARAMS

    def test_search_allowed_params_spatial_facets(self):
        """Test that SEARCH_ALLOWED_PARAMS contains spatial facet parameters."""
        assert "fq[geo_country_agg][]" in SEARCH_ALLOWED_PARAMS
        assert "fq[geo_region_agg][]" in SEARCH_ALLOWED_PARAMS
        assert "fq[geo_county_agg][]" in SEARCH_ALLOWED_PARAMS

    def test_gazetteer_allowed_params_structure(self):
        """Test that GAZETTEER_ALLOWED_PARAMS contains expected parameters."""
        assert isinstance(GAZETTEER_ALLOWED_PARAMS, list)
        assert len(GAZETTEER_ALLOWED_PARAMS) > 0
        
        # Check core gazetteer parameters
        assert "q" in GAZETTEER_ALLOWED_PARAMS
        assert "limit" in GAZETTEER_ALLOWED_PARAMS
        assert "offset" in GAZETTEER_ALLOWED_PARAMS
        assert "callback" in GAZETTEER_ALLOWED_PARAMS

    def test_resource_allowed_params_structure(self):
        """Test that RESOURCE_ALLOWED_PARAMS contains expected parameters."""
        assert isinstance(RESOURCE_ALLOWED_PARAMS, list)
        assert len(RESOURCE_ALLOWED_PARAMS) > 0
        
        # Check resource parameters
        assert "callback" in RESOURCE_ALLOWED_PARAMS

    def test_admin_allowed_params_structure(self):
        """Test that ADMIN_ALLOWED_PARAMS contains expected parameters."""
        assert isinstance(ADMIN_ALLOWED_PARAMS, list)
        assert len(ADMIN_ALLOWED_PARAMS) > 0
        
        # Check admin parameters
        assert "callback" in ADMIN_ALLOWED_PARAMS

    def test_mcp_allowed_params_structure(self):
        """Test that MCP_ALLOWED_PARAMS contains expected parameters."""
        assert isinstance(MCP_ALLOWED_PARAMS, list)
        assert len(MCP_ALLOWED_PARAMS) > 0
        
        # Check MCP parameters
        assert "callback" in MCP_ALLOWED_PARAMS

    def test_shapefile_allowed_params_structure(self):
        """Test that SHAPEFILE_ALLOWED_PARAMS contains expected parameters."""
        assert isinstance(SHAPEFILE_ALLOWED_PARAMS, list)
        assert len(SHAPEFILE_ALLOWED_PARAMS) > 0
        
        # Check shapefile parameters
        assert "callback" in SHAPEFILE_ALLOWED_PARAMS

    def test_thumbnail_allowed_params_structure(self):
        """Test that THUMBNAIL_ALLOWED_PARAMS contains expected parameters."""
        assert isinstance(THUMBNAIL_ALLOWED_PARAMS, list)
        assert len(THUMBNAIL_ALLOWED_PARAMS) > 0
        
        # Check thumbnail parameters
        assert "callback" in THUMBNAIL_ALLOWED_PARAMS

    def test_all_params_are_strings(self):
        """Test that all parameters in all lists are strings."""
        all_param_lists = [
            SEARCH_ALLOWED_PARAMS,
            GAZETTEER_ALLOWED_PARAMS,
            RESOURCE_ALLOWED_PARAMS,
            ADMIN_ALLOWED_PARAMS,
            MCP_ALLOWED_PARAMS,
            SHAPEFILE_ALLOWED_PARAMS,
            THUMBNAIL_ALLOWED_PARAMS,
        ]
        
        for param_list in all_param_lists:
            for param in param_list:
                assert isinstance(param, str), f"Parameter {param} should be a string"

    def test_no_duplicate_parameters_in_search(self):
        """Test that SEARCH_ALLOWED_PARAMS has no duplicate parameters."""
        assert len(SEARCH_ALLOWED_PARAMS) == len(set(SEARCH_ALLOWED_PARAMS))

    def test_no_duplicate_parameters_in_gazetteer(self):
        """Test that GAZETTEER_ALLOWED_PARAMS has no duplicate parameters."""
        assert len(GAZETTEER_ALLOWED_PARAMS) == len(set(GAZETTEER_ALLOWED_PARAMS))

    def test_facet_filter_format_consistency(self):
        """Test that facet filter parameters follow consistent naming pattern."""
        facet_params = [param for param in SEARCH_ALLOWED_PARAMS if param.startswith("fq[") and param.endswith("[]")]
        
        for param in facet_params:
            # Should be in format fq[aggregation_name][]
            assert param.startswith("fq[")
            assert param.endswith("[]")
            # Should have content between fq[ and ][]
            content = param[3:-2]  # Remove "fq[" and "][]"
            assert len(content) > 0
            assert "_agg" in content, f"Facet parameter {param} should contain '_agg'"

    def test_spatial_facet_naming_consistency(self):
        """Test that spatial facet parameters follow consistent naming pattern."""
        spatial_params = [param for param in SEARCH_ALLOWED_PARAMS if "geo_" in param]
        
        expected_spatial_params = [
            "fq[geo_country_agg][]",
            "fq[geo_region_agg][]", 
            "fq[geo_county_agg][]"
        ]
        
        for expected_param in expected_spatial_params:
            assert expected_param in spatial_params

    def test_search_params_comprehensive_coverage(self):
        """Test that SEARCH_ALLOWED_PARAMS covers all expected parameter categories."""
        # Core search parameters
        core_params = ["q", "page", "per_page", "sort", "callback"]
        for param in core_params:
            assert param in SEARCH_ALLOWED_PARAMS
        
        # Facet filter parameters (should have _agg in name)
        facet_params = [param for param in SEARCH_ALLOWED_PARAMS if "_agg" in param]
        assert len(facet_params) > 10  # Should have many facet parameters
        
        # Spatial facet parameters
        spatial_params = [param for param in SEARCH_ALLOWED_PARAMS if "geo_" in param]
        assert len(spatial_params) >= 3  # Should have geo_country, geo_region, geo_county

    def test_gazetteer_params_minimal_but_complete(self):
        """Test that GAZETTEER_ALLOWED_PARAMS is minimal but covers essential functionality."""
        assert len(GAZETTEER_ALLOWED_PARAMS) == 4  # Should be exactly 4 parameters
        assert "q" in GAZETTEER_ALLOWED_PARAMS  # Search query
        assert "limit" in GAZETTEER_ALLOWED_PARAMS  # Result limit
        assert "offset" in GAZETTEER_ALLOWED_PARAMS  # Pagination offset
        assert "callback" in GAZETTEER_ALLOWED_PARAMS  # JSONP callback

    def test_simple_endpoints_have_minimal_params(self):
        """Test that simple endpoints only have callback parameter."""
        simple_endpoints = [
            RESOURCE_ALLOWED_PARAMS,
            ADMIN_ALLOWED_PARAMS,
            MCP_ALLOWED_PARAMS,
            SHAPEFILE_ALLOWED_PARAMS,
            THUMBNAIL_ALLOWED_PARAMS,
        ]
        
        for params in simple_endpoints:
            assert len(params) == 1  # Should only have callback
            assert "callback" in params

    def test_parameter_names_are_snake_case_or_brackets(self):
        """Test that parameter names follow consistent naming conventions."""
        all_params = []
        for param_list in [
            SEARCH_ALLOWED_PARAMS,
            GAZETTEER_ALLOWED_PARAMS,
            RESOURCE_ALLOWED_PARAMS,
            ADMIN_ALLOWED_PARAMS,
            MCP_ALLOWED_PARAMS,
            SHAPEFILE_ALLOWED_PARAMS,
            THUMBNAIL_ALLOWED_PARAMS,
        ]:
            all_params.extend(param_list)
        
        for param in all_params:
            # Should be either simple snake_case or bracket notation
            if "[" in param:
                # Bracket notation like fq[param_name][]
                assert param.endswith("[]")
                assert "[" in param and "]" in param
            else:
                # Simple snake_case like per_page, callback
                assert "_" in param or param.isalpha(), f"Parameter {param} should use snake_case or be alphabetic"