"""
Tests for the OGM Field Mapper service.
"""

import pytest
from app.services.ogm_field_mapper import OGMFieldMapper


class TestOGMFieldMapper:
    """Test cases for OGMFieldMapper class."""

    def test_map_resource_fields_standard_fields(self):
        """Test mapping of standard OGM Aardvark fields."""
        # Database response with downcased field names
        db_resource = {
            "id": "test-123",
            "gbl_mdversion_s": "Aardvark",
            "gbl_mdmodified_dt": "2024-01-01T00:00:00Z",
            "gbl_resourceclass_sm": ["Datasets"],
            "gbl_resourcetype_sm": ["Vector data"],
            "gbl_indexyear_im": [2024],
            "gbl_daterange_drsim": ["[2024 TO 2024]"],
            "gbl_filesize_s": "1.2 MB",
            "gbl_wxsidentifier_s": "test-wxs-id",
            "gbl_suppressed_b": False,
            "gbl_georeferenced_b": True,
            "gbl_displaynote_sm": ["Test note"],
            "dct_accessrights_s": "Public",
            "dct_rightsholder_sm": ["Test Holder"],
            "dct_ispartof_sm": ["Test Collection"],
            "dct_isversionof_sm": ["Test Version"],
            "dct_isreplacedby_sm": ["Test Replacement"],
            "pcdm_memberof_sm": ["Test Member"],
        }

        # Expected result with proper OGM field names
        expected = {
            "id": "test-123",
            "gbl_mdVersion_s": "Aardvark",
            "gbl_mdModified_dt": "2024-01-01T00:00:00Z",
            "gbl_resourceClass_sm": ["Datasets"],
            "gbl_resourceType_sm": ["Vector data"],
            "gbl_indexYear_im": [2024],
            "gbl_dateRange_drsim": ["[2024 TO 2024]"],
            "gbl_fileSize_s": "1.2 MB",
            "gbl_wxsIdentifier_s": "test-wxs-id",
            "gbl_suppressed_b": False,
            "gbl_georeferenced_b": True,
            "gbl_displayNote_sm": ["Test note"],
            "dct_accessRights_s": "Public",
            "dct_rightsHolder_sm": ["Test Holder"],
            "dct_isPartOf_sm": ["Test Collection"],
            "dct_isVersionOf_sm": ["Test Version"],
            "dct_isReplacedBy_sm": ["Test Replacement"],
            "pcdm_memberOf_sm": ["Test Member"],
        }

        result = OGMFieldMapper.map_resource_fields(db_resource)
        assert result == expected

    def test_map_resource_fields_btaa_fields(self):
        """Test mapping of BTAA-specific fields."""
        # Database response with BTAA fields
        db_resource = {
            "id": "test-123",
            "b1g_code_s": "TEST001",
            "b1g_status_s": "active",
            "b1g_dct_accrualmethod_s": "periodic",
            "b1g_dct_accrualperiodicity_s": "monthly",
            "b1g_dateaccessioned_s": "2024-01-01",
            "b1g_dateretired_s": None,
            "b1g_child_record_b": False,
            "b1g_dct_mediator_sm": ["mediator1", "mediator2"],
            "b1g_access_s": {"public": "https://example.com"},
            "b1g_image_ss": "https://example.com/image.jpg",
            "b1g_geonames_sm": ["https://sws.geonames.org/12345/"],
            "b1g_publication_state_s": "published",
            "b1g_language_sm": ["eng"],
            "b1g_creatorid_sm": ["https://orcid.org/0000-0000-0000-0000"],
            "b1g_dct_conformsto_sm": ["https://example.com/schema"],
            "b1g_dcat_spatialresolutioninmeters_sm": ["30"],
            "b1g_geodcat_spatialresolutionastext_sm": ["30 meters"],
            "b1g_dct_provenancestatement_sm": ["Provenance statement"],
            "b1g_admintags_sm": ["tag1", "tag2"],
        }

        # Expected result with proper BTAA field names
        expected = {
            "id": "test-123",
            "b1g_code_s": "TEST001",
            "b1g_status_s": "active",
            "b1g_dct_accrualMethod_s": "periodic",
            "b1g_dct_accrualPeriodicity_s": "monthly",
            "b1g_dateAccessioned_s": "2024-01-01",
            "b1g_dateRetired_s": None,
            "b1g_child_record_b": False,
            "b1g_dct_mediator_sm": ["mediator1", "mediator2"],
            "b1g_access_s": {"public": "https://example.com"},
            "b1g_image_ss": "https://example.com/image.jpg",
            "b1g_geonames_sm": ["https://sws.geonames.org/12345/"],
            "b1g_publication_state_s": "published",
            "b1g_language_sm": ["eng"],
            "b1g_creatorID_sm": ["https://orcid.org/0000-0000-0000-0000"],
            "b1g_dct_conformsTo_sm": ["https://example.com/schema"],
            "b1g_dcat_spatialResolutionInMeters_sm": ["30"],
            "b1g_geodcat_spatialResolutionAsText_sm": ["30 meters"],
            "b1g_dct_provenanceStatement_sm": ["Provenance statement"],
            "b1g_adminTags_sm": ["tag1", "tag2"],
        }

        result = OGMFieldMapper.map_resource_fields(db_resource)
        assert result == expected

    def test_map_resource_fields_mixed_fields(self):
        """Test mapping with both standard and BTAA fields."""
        db_resource = {
            "id": "test-123",
            "dct_title_s": "Test Title",
            "dct_description_sm": ["Test description"],
            "gbl_resourceclass_sm": ["Datasets"],
            "b1g_code_s": "TEST001",
            "b1g_status_s": "active",
            "unknown_field": "unknown value",
        }

        expected = {
            "id": "test-123",
            "dct_title_s": "Test Title",  # No mapping needed
            "dct_description_sm": ["Test description"],  # No mapping needed
            "gbl_resourceClass_sm": ["Datasets"],  # Mapped
            "b1g_code_s": "TEST001",  # No mapping needed
            "b1g_status_s": "active",  # No mapping needed
            "unknown_field": "unknown value",  # No mapping, kept as-is
        }

        result = OGMFieldMapper.map_resource_fields(db_resource)
        assert result == expected

    def test_map_resource_fields_empty_dict(self):
        """Test mapping with empty dictionary."""
        result = OGMFieldMapper.map_resource_fields({})
        assert result == {}

    def test_get_required_fields(self):
        """Test getting required fields list."""
        required_fields = OGMFieldMapper.get_required_fields()
        
        # Check that all required fields are present
        expected_required = [
            "id", "gbl_mdVersion_s", "schema_provider_s", "dct_title_s",
            "dct_description_sm", "dct_language_sm", "dct_accessRights_s",
            "dct_license_sm", "b1g_code_s", "b1g_dct_accrualMethod_s",
            "b1g_dateAccessioned_s", "b1g_publication_state_s", "b1g_language_sm"
        ]
        
        for field in expected_required:
            assert field in required_fields

    def test_get_all_schema_fields(self):
        """Test getting all schema fields list."""
        all_fields = OGMFieldMapper.get_all_schema_fields()
        
        # Check that some key fields are present
        expected_fields = [
            "gbl_mdVersion_s", "gbl_resourceClass_sm", "b1g_code_s",
            "b1g_status_s", "dct_title_s", "dct_description_sm"
        ]
        
        for field in expected_fields:
            assert field in all_fields
