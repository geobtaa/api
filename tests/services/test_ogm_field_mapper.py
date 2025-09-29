"""
Tests for the OGMFieldMapper service.
"""

import pytest

from app.services.ogm_field_mapper import OGMFieldMapper


class TestOGMFieldMapper:
    """Test cases for OGMFieldMapper class."""

    def test_field_mapping_exists(self):
        """Test that the field mapping dictionary exists and is not empty."""
        assert hasattr(OGMFieldMapper, 'FIELD_MAPPING')
        assert isinstance(OGMFieldMapper.FIELD_MAPPING, dict)
        assert len(OGMFieldMapper.FIELD_MAPPING) > 0

    def test_field_mapping_contains_standard_ogm_fields(self):
        """Test that the field mapping contains standard OGM fields."""
        mapping = OGMFieldMapper.FIELD_MAPPING
        
        # Test some standard OGM fields
        assert "gbl_mdversion_s" in mapping
        assert mapping["gbl_mdversion_s"] == "gbl_mdVersion_s"
        
        assert "gbl_mdmodified_dt" in mapping
        assert mapping["gbl_mdmodified_dt"] == "gbl_mdModified_dt"
        
        assert "gbl_resourceclass_sm" in mapping
        assert mapping["gbl_resourceclass_sm"] == "gbl_resourceClass_sm"
        
        assert "gbl_resourcetype_sm" in mapping
        assert mapping["gbl_resourcetype_sm"] == "gbl_resourceType_sm"

    def test_field_mapping_contains_btaa_specific_fields(self):
        """Test that the field mapping contains BTAA-specific fields."""
        mapping = OGMFieldMapper.FIELD_MAPPING
        
        # Test some BTAA-specific fields
        assert "b1g_code_s" in mapping
        assert mapping["b1g_code_s"] == "b1g_code_s"  # No change needed
        
        assert "b1g_status_s" in mapping
        assert mapping["b1g_status_s"] == "b1g_status_s"  # No change needed
        
        assert "b1g_dct_accrualmethod_s" in mapping
        assert mapping["b1g_dct_accrualmethod_s"] == "b1g_dct_accrualMethod_s"
        
        assert "b1g_dct_accrualperiodicity_s" in mapping
        assert mapping["b1g_dct_accrualperiodicity_s"] == "b1g_dct_accrualPeriodicity_s"

    def test_field_mapping_contains_dct_fields(self):
        """Test that the field mapping contains DCT fields."""
        mapping = OGMFieldMapper.FIELD_MAPPING
        
        # Test some DCT fields
        assert "dct_accessrights_s" in mapping
        assert mapping["dct_accessrights_s"] == "dct_accessRights_s"
        
        assert "dct_rightsholder_sm" in mapping
        assert mapping["dct_rightsholder_sm"] == "dct_rightsHolder_sm"
        
        assert "dct_ispartof_sm" in mapping
        assert mapping["dct_ispartof_sm"] == "dct_isPartOf_sm"

    def test_map_resource_fields_empty_dict(self):
        """Test mapping an empty resource dictionary."""
        result = OGMFieldMapper.map_resource_fields({})
        
        assert isinstance(result, dict)
        assert len(result) == 0

    def test_map_resource_fields_no_mapping_needed(self):
        """Test mapping a resource dictionary with fields that don't need mapping."""
        resource_dict = {
            "id": "test_id",
            "dct_title_s": "Test Title",
            "dct_description_sm": "Test Description"
        }
        
        result = OGMFieldMapper.map_resource_fields(resource_dict)
        
        assert isinstance(result, dict)
        assert result["id"] == "test_id"
        assert result["dct_title_s"] == "Test Title"
        assert result["dct_description_sm"] == "Test Description"

    def test_map_resource_fields_with_mapping_needed(self):
        """Test mapping a resource dictionary with fields that need mapping."""
        resource_dict = {
            "id": "test_id",
            "gbl_mdversion_s": "2.0",
            "gbl_resourceclass_sm": "Datasets",
            "dct_title_s": "Test Title"
        }
        
        result = OGMFieldMapper.map_resource_fields(resource_dict)
        
        assert isinstance(result, dict)
        assert result["id"] == "test_id"
        assert result["gbl_mdVersion_s"] == "2.0"  # Mapped
        assert result["gbl_resourceClass_sm"] == "Datasets"  # Mapped
        assert result["dct_title_s"] == "Test Title"  # No mapping needed

    def test_map_resource_fields_mixed_types(self):
        """Test mapping a resource dictionary with various data types."""
        resource_dict = {
            "gbl_mdversion_s": "2.0",
            "gbl_indexyear_im": 2023,
            "gbl_georeferenced_b": True,
            "gbl_daterange_drsim": ["2020-01-01", "2023-12-31"],
            "dct_creator_sm": ["Creator 1", "Creator 2"],
            "dcat_bbox": {"type": "Polygon", "coordinates": [[[1, 2], [3, 4]]]}
        }
        
        result = OGMFieldMapper.map_resource_fields(resource_dict)
        
        assert isinstance(result, dict)
        assert result["gbl_mdVersion_s"] == "2.0"
        assert result["gbl_indexYear_im"] == 2023
        assert result["gbl_georeferenced_b"] is True
        assert result["gbl_dateRange_drsim"] == ["2020-01-01", "2023-12-31"]
        assert result["dct_creator_sm"] == ["Creator 1", "Creator 2"]
        assert result["dcat_bbox"]["type"] == "Polygon"

    def test_map_resource_fields_comprehensive(self):
        """Test mapping a comprehensive resource dictionary."""
        resource_dict = {
            # Standard OGM fields
            "gbl_mdversion_s": "2.0",
            "gbl_mdmodified_dt": "2023-01-01T00:00:00Z",
            "gbl_resourceclass_sm": "Datasets",
            "gbl_resourcetype_sm": "Vector",
            "gbl_indexyear_im": 2023,
            "gbl_daterange_drsim": ["2020-01-01", "2023-12-31"],
            "gbl_filesize_s": "1024KB",
            "gbl_wxsidentifier_s": "test-wxs-id",
            "gbl_suppressed_b": False,
            "gbl_georeferenced_b": True,
            "gbl_displaynote_sm": "Test note",
            
            # BTAA-specific fields
            "b1g_code_s": "BTA-001",
            "b1g_status_s": "active",
            "b1g_dct_accrualmethod_s": "RPA",
            "b1g_dct_accrualperiodicity_s": "irregular",
            "b1g_dateaccessioned_s": "2023-01-01",
            "b1g_child_record_b": False,
            "b1g_dct_mediator_sm": ["Mediator 1"],
            "b1g_access_s": "public",
            "b1g_image_ss": ["image1.jpg", "image2.jpg"],
            "b1g_geonames_sm": ["Minnesota", "Minneapolis"],
            "b1g_publication_state_s": "published",
            "b1g_language_sm": ["en"],
            "b1g_creatorid_sm": ["creator-001"],
            "b1g_dct_conformsto_sm": ["ISO 19115"],
            "b1g_dcat_spatialresolutioninmeters_sm": ["10"],
            "b1g_geodcat_spatialresolutionastext_sm": ["10 meters"],
            "b1g_dct_provenancestatement_sm": ["Test provenance"],
            "b1g_admintags_sm": ["admin-tag-1"],
            
            # DCT fields
            "dct_accessrights_s": "public",
            "dct_rightsholder_sm": ["Right Holder"],
            "dct_ispartof_sm": ["Collection 1"],
            "dct_isversionof_sm": ["Version 1"],
            "dct_isreplacedby_sm": ["Replacement 1"],
            "pcdm_memberof_sm": ["Collection 1"],
            
            # Other fields
            "layer_geom_type_s": "polygon",
            "solr_year_i": 2023,
            "layer_id_s": "layer-001",
            "suppressed_b": False,
            
            # Fields that don't need mapping
            "id": "resource-001",
            "dct_title_s": "Test Resource",
            "dct_description_sm": "Test description"
        }
        
        result = OGMFieldMapper.map_resource_fields(resource_dict)
        
        # Verify all fields are present
        assert len(result) == len(resource_dict)
        
        # Verify specific mappings
        assert result["gbl_mdVersion_s"] == "2.0"
        assert result["gbl_mdModified_dt"] == "2023-01-01T00:00:00Z"
        assert result["gbl_resourceClass_sm"] == "Datasets"
        assert result["gbl_resourceType_sm"] == "Vector"
        assert result["gbl_indexYear_im"] == 2023
        assert result["gbl_dateRange_drsim"] == ["2020-01-01", "2023-12-31"]
        assert result["gbl_fileSize_s"] == "1024KB"
        assert result["gbl_wxsIdentifier_s"] == "test-wxs-id"
        assert result["gbl_suppressed_b"] is False
        assert result["gbl_georeferenced_b"] is True
        assert result["gbl_displayNote_sm"] == "Test note"
        
        # Verify BTAA fields
        assert result["b1g_dct_accrualMethod_s"] == "RPA"
        assert result["b1g_dct_accrualPeriodicity_s"] == "irregular"
        assert result["b1g_dateAccessioned_s"] == "2023-01-01"
        assert result["b1g_child_record_b"] is False
        assert result["b1g_dct_mediator_sm"] == ["Mediator 1"]
        assert result["b1g_dcat_spatialResolutionInMeters_sm"] == ["10"]
        assert result["b1g_geodcat_spatialResolutionAsText_sm"] == ["10 meters"]
        assert result["b1g_dct_provenanceStatement_sm"] == ["Test provenance"]
        assert result["b1g_adminTags_sm"] == ["admin-tag-1"]
        
        # Verify DCT fields
        assert result["dct_accessRights_s"] == "public"
        assert result["dct_rightsHolder_sm"] == ["Right Holder"]
        assert result["dct_isPartOf_sm"] == ["Collection 1"]
        assert result["dct_isVersionOf_sm"] == ["Version 1"]
        assert result["dct_isReplacedBy_sm"] == ["Replacement 1"]
        assert result["pcdm_memberOf_sm"] == ["Collection 1"]
        
        # Verify fields that don't need mapping remain unchanged
        assert result["id"] == "resource-001"
        assert result["dct_title_s"] == "Test Resource"
        assert result["dct_description_sm"] == "Test description"
        assert result["b1g_code_s"] == "BTA-001"
        assert result["b1g_status_s"] == "active"

    def test_map_resource_fields_none_values(self):
        """Test mapping a resource dictionary with None values."""
        resource_dict = {
            "gbl_mdversion_s": None,
            "gbl_resourceclass_sm": "Datasets",
            "dct_title_s": None
        }
        
        result = OGMFieldMapper.map_resource_fields(resource_dict)
        
        assert result["gbl_mdVersion_s"] is None
        assert result["gbl_resourceClass_sm"] == "Datasets"
        assert result["dct_title_s"] is None

    def test_map_resource_fields_empty_strings(self):
        """Test mapping a resource dictionary with empty strings."""
        resource_dict = {
            "gbl_mdversion_s": "",
            "gbl_resourceclass_sm": "Datasets",
            "dct_title_s": ""
        }
        
        result = OGMFieldMapper.map_resource_fields(resource_dict)
        
        assert result["gbl_mdVersion_s"] == ""
        assert result["gbl_resourceClass_sm"] == "Datasets"
        assert result["dct_title_s"] == ""

    def test_map_resource_fields_zero_values(self):
        """Test mapping a resource dictionary with zero values."""
        resource_dict = {
            "gbl_indexyear_im": 0,
            "gbl_georeferenced_b": False,
            "gbl_suppressed_b": False
        }
        
        result = OGMFieldMapper.map_resource_fields(resource_dict)
        
        assert result["gbl_indexYear_im"] == 0
        assert result["gbl_georeferenced_b"] is False
        assert result["gbl_suppressed_b"] is False

    def test_get_required_fields(self):
        """Test getting the list of required fields."""
        required_fields = OGMFieldMapper.get_required_fields()
        
        assert isinstance(required_fields, list)
        assert len(required_fields) > 0
        
        # Check that all required fields are present
        expected_required = [
            "id",
            "gbl_mdVersion_s",
            "schema_provider_s",
            "dct_title_s",
            "dct_description_sm",
            "dct_language_sm",
            "dct_accessRights_s",
            "dct_license_sm",
            "b1g_code_s",
            "b1g_dct_accrualMethod_s",
            "b1g_dateAccessioned_s",
            "b1g_publication_state_s",
            "b1g_language_sm",
        ]
        
        for field in expected_required:
            assert field in required_fields

    def test_get_required_fields_structure(self):
        """Test the structure of required fields list."""
        required_fields = OGMFieldMapper.get_required_fields()
        
        # All should be strings
        for field in required_fields:
            assert isinstance(field, str)
            assert len(field) > 0
        
        # Should contain no duplicates
        assert len(required_fields) == len(set(required_fields))

    def test_get_all_schema_fields(self):
        """Test getting the list of all schema fields."""
        all_fields = OGMFieldMapper.get_all_schema_fields()
        
        assert isinstance(all_fields, list)
        assert len(all_fields) > 0
        
        # Check that mapped fields are included
        mapped_fields = list(OGMFieldMapper.FIELD_MAPPING.values())
        for field in mapped_fields:
            assert field in all_fields
        
        # Check that additional fields are included
        additional_fields = [
            "id",
            "dct_title_s",
            "dct_description_sm",
            "dct_alternative_sm",
            "dct_subject_sm",
            "dct_creator_sm",
            "dct_publisher_sm",
            "dct_rights_sm",
            "dct_source_sm",
            "dct_replaces_sm",
            "dct_relation_sm",
            "dct_issued_s",
            "dct_temporal_sm",
            "dct_spatial_sm",
            "dcat_bbox",
            "dcat_centroid",
            "locn_geometry",
            "dct_references_s",
            "dct_identifier_sm",
            "dct_format_s",
        ]
        
        for field in additional_fields:
            assert field in all_fields

    def test_get_all_schema_fields_structure(self):
        """Test the structure of all schema fields list."""
        all_fields = OGMFieldMapper.get_all_schema_fields()
        
        # All should be strings
        for field in all_fields:
            assert isinstance(field, str)
            assert len(field) > 0
        
        # Should contain no duplicates
        assert len(all_fields) == len(set(all_fields))
        
        # Should be longer than just the mapped fields
        mapped_fields = list(OGMFieldMapper.FIELD_MAPPING.values())
        assert len(all_fields) > len(mapped_fields)

    def test_field_mapping_consistency(self):
        """Test that field mapping is consistent (no circular mappings)."""
        mapping = OGMFieldMapper.FIELD_MAPPING
        
        # Some fields may map to themselves (unchanged), which is valid
        # We just ensure no two different fields map to the same OGM field
        ogm_fields = list(mapping.values())
        assert len(ogm_fields) == len(set(ogm_fields)), "Duplicate OGM field mappings found"

    def test_field_mapping_camelcase_conversion(self):
        """Test that field mapping correctly converts camelCase."""
        mapping = OGMFieldMapper.FIELD_MAPPING
        
        # Test specific camelCase conversions
        assert "gbl_mdversion_s" in mapping
        assert mapping["gbl_mdversion_s"] == "gbl_mdVersion_s"
        
        assert "gbl_resourceclass_sm" in mapping
        assert mapping["gbl_resourceclass_sm"] == "gbl_resourceClass_sm"
        
        assert "gbl_resourcetype_sm" in mapping
        assert mapping["gbl_resourcetype_sm"] == "gbl_resourceType_sm"
        
        assert "gbl_indexyear_im" in mapping
        assert mapping["gbl_indexyear_im"] == "gbl_indexYear_im"

    def test_field_mapping_preserves_unchanged_fields(self):
        """Test that fields that don't need mapping are preserved."""
        mapping = OGMFieldMapper.FIELD_MAPPING
        
        # Some fields should remain unchanged
        unchanged_fields = [
            "b1g_code_s",
            "b1g_status_s",
            "layer_geom_type_s",
            "solr_year_i",
            "layer_id_s",
            "suppressed_b"
        ]
        
        for field in unchanged_fields:
            assert field in mapping
            assert mapping[field] == field

    def test_map_resource_fields_preserves_original(self):
        """Test that map_resource_fields doesn't modify the original dictionary."""
        original_dict = {
            "gbl_mdversion_s": "2.0",
            "dct_title_s": "Test Title"
        }
        
        original_copy = original_dict.copy()
        result = OGMFieldMapper.map_resource_fields(original_dict)
        
        # Original should be unchanged
        assert original_dict == original_copy
        
        # Result should be different (mapped)
        assert result != original_dict
        assert "gbl_mdVersion_s" in result
        assert "gbl_mdversion_s" not in result
