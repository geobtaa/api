"""
Tests for the elasticsearch mappings module.
"""

from app.elasticsearch.mappings import INDEX_MAPPING


class TestMappings:
    """Test cases for elasticsearch mappings module."""

    def test_index_mapping_structure(self):
        """Test that INDEX_MAPPING has the correct top-level structure."""
        assert isinstance(INDEX_MAPPING, dict)
        assert "mappings" in INDEX_MAPPING
        assert "settings" in INDEX_MAPPING

    def test_mappings_properties_structure(self):
        """Test that mappings.properties has the expected structure."""
        mappings = INDEX_MAPPING["mappings"]
        assert "properties" in mappings

        properties = mappings["properties"]
        assert isinstance(properties, dict)
        assert len(properties) > 0

    def test_core_field_mappings(self):
        """Test that core field mappings are present and correctly configured."""
        properties = INDEX_MAPPING["mappings"]["properties"]

        # Test ID field
        assert "id" in properties
        assert properties["id"]["type"] == "keyword"

        # Test title field with text and keyword
        assert "dct_title_s" in properties
        title_field = properties["dct_title_s"]
        assert title_field["type"] == "text"
        assert "fields" in title_field
        assert "keyword" in title_field["fields"]
        assert title_field["fields"]["keyword"]["type"] == "keyword"
        assert title_field["fields"]["keyword"]["normalizer"] == "lowercase"

    def test_spatial_field_mappings(self):
        """Test that spatial field mappings are correctly configured."""
        properties = INDEX_MAPPING["mappings"]["properties"]

        # Test geometry field
        assert "locn_geometry" in properties
        geometry_field = properties["locn_geometry"]
        assert geometry_field["type"] == "geo_shape"
        assert geometry_field["orientation"] == "counterclockwise"
        assert geometry_field["coerce"] is True

        # Test bbox field
        assert "dcat_bbox" in properties
        bbox_field = properties["dcat_bbox"]
        assert bbox_field["type"] == "geo_shape"
        assert bbox_field["orientation"] == "counterclockwise"
        assert bbox_field["coerce"] is True

        # Test centroid field
        assert "dcat_centroid" in properties
        centroid_field = properties["dcat_centroid"]
        assert centroid_field["type"] == "geo_point"

    def test_facet_field_mappings(self):
        """Test that facet field mappings are present."""
        properties = INDEX_MAPPING["mappings"]["properties"]

        # Test spatial facet fields
        assert "geo_country" in properties
        assert properties["geo_country"]["type"] == "keyword"

        assert "geo_region" in properties
        assert properties["geo_region"]["type"] == "keyword"

        assert "geo_county" in properties
        assert properties["geo_county"]["type"] == "keyword"

    def test_btaa_specific_field_mappings(self):
        """Test that BTAA-specific field mappings are present."""
        properties = INDEX_MAPPING["mappings"]["properties"]

        # Test BTAA fields
        btaa_fields = [
            "b1g_code_s",
            "b1g_status_s",
            "b1g_dct_accrualMethod_s",
            "b1g_dct_accrualPeriodicity_s",
            "b1g_dateAccessioned_s",
            "b1g_dateRetired_s",
            "b1g_child_record_b",
            "b1g_dct_mediator_sm",
            "b1g_access_s",
            "b1g_image_ss",
            "b1g_geonames_sm",
            "b1g_publication_state_s",
            "b1g_language_sm",
            "b1g_creatorID_sm",
            "b1g_dct_conformsTo_sm",
            "b1g_dcat_spatialResolutionInMeters_sm",
            "b1g_geodcat_spatialResolutionAsText_sm",
            "b1g_dct_provenanceStatement_sm",
            "b1g_adminTags_sm",
        ]

        for field in btaa_fields:
            assert field in properties, f"BTAA field {field} should be in mappings"

    def test_suggest_field_mapping(self):
        """Test that the suggest field is correctly configured for autocomplete."""
        properties = INDEX_MAPPING["mappings"]["properties"]

        assert "suggest" in properties
        suggest_field = properties["suggest"]
        assert suggest_field["type"] == "completion"
        assert suggest_field["analyzer"] == "simple"
        assert suggest_field["preserve_separators"] is True
        assert suggest_field["preserve_position_increments"] is True
        assert suggest_field["max_input_length"] == 50

    def test_index_settings_structure(self):
        """Test that index settings are correctly configured."""
        settings = INDEX_MAPPING["settings"]
        assert "index" in settings

        index_settings = settings["index"]
        assert index_settings["number_of_shards"] == 1
        # Replicas should be 0 for single-node development clusters (or 1 for production)
        assert index_settings["number_of_replicas"] in [0, 1]

        # Test analysis settings
        assert "analysis" in index_settings
        analysis = index_settings["analysis"]
        assert "normalizer" in analysis

        # Test lowercase normalizer
        normalizer = analysis["normalizer"]
        assert "lowercase" in normalizer
        assert normalizer["lowercase"]["type"] == "custom"
        assert normalizer["lowercase"]["char_filter"] == []
        assert normalizer["lowercase"]["filter"] == ["lowercase"]

    def test_field_type_consistency(self):
        """Test that field types are consistent and appropriate."""
        properties = INDEX_MAPPING["mappings"]["properties"]

        # Text fields should have appropriate configuration
        text_fields = [
            "dct_title_s",
            "dct_alternative_sm",
            "dct_description_sm",
            "gbl_displaynote_sm",
            "dct_publisher_sm",
            "dct_subject_sm",
            "dcat_theme_sm",
            "dcat_keyword_sm",
            "summary",
        ]

        for field in text_fields:
            if field in properties:
                assert properties[field]["type"] == "text"

        # Date-ish fields that often contain free-form or fuzzy text (e.g. "1656-1677?" or
        # "2021-08-31 to *") are indexed as keywords to prevent Elasticsearch from trying
        # to parse them as strict dates
        keyword_date_fields = [
            "dct_temporal_sm",
            "dct_issued_s",
            "gbl_daterange_drsim",
        ]

        for field in keyword_date_fields:
            if field in properties:
                assert properties[field]["type"] == "keyword"

        # Fields that were keywords are now text with a keyword subfield
        text_with_keyword_fields = [
            "dct_spatial_sm",
            "gbl_resourceClass_sm",
            "gbl_resourceType_sm",
            "dct_language_sm",
            "dct_creator_sm",
            "schema_provider_s",
            "dct_accessRights_s",
        ]

        for field in text_with_keyword_fields:
            if field in properties:
                assert properties[field]["type"] == "text"
                assert "fields" in properties[field]
                assert "keyword" in properties[field]["fields"]
                assert properties[field]["fields"]["keyword"]["type"] == "keyword"

        # Boolean fields should be configured as booleans
        boolean_fields = ["gbl_georeferenced_b", "b1g_child_record_b"]

        for field in boolean_fields:
            if field in properties:
                assert properties[field]["type"] == "boolean"

        # Integer fields should be configured as integers
        integer_fields = ["gbl_indexYear_im"]

        for field in integer_fields:
            if field in properties:
                assert properties[field]["type"] == "integer"

    def test_date_field_mappings(self):
        """Test that date field mappings are correctly configured."""
        properties = INDEX_MAPPING["mappings"]["properties"]

        date_fields = ["gbl_mdmodified_dt", "b1g_dateAccessioned_s", "b1g_dateRetired_s"]

        for field in date_fields:
            if field in properties:
                assert properties[field]["type"] == "date"

    def test_object_field_mappings(self):
        """Test that object field mappings are correctly configured."""
        properties = INDEX_MAPPING["mappings"]["properties"]

        # Test object fields that are disabled
        object_fields = ["dct_references_s", "b1g_access_s"]

        for field in object_fields:
            if field in properties:
                assert properties[field]["type"] == "object"
                assert properties[field]["enabled"] is False

    def test_mapping_completeness(self):
        """Test that all expected fields are present in the mapping."""
        properties = INDEX_MAPPING["mappings"]["properties"]

        # Check that we have a reasonable number of fields
        assert len(properties) >= 50  # Should have many fields

        # Check for key field categories
        has_text_fields = any(prop.get("type") == "text" for prop in properties.values())
        has_keyword_fields = any(prop.get("type") == "keyword" for prop in properties.values())
        has_geo_fields = any(
            prop.get("type") in ["geo_shape", "geo_point"] for prop in properties.values()
        )
        has_completion_fields = any(
            prop.get("type") == "completion" for prop in properties.values()
        )

        assert has_text_fields
        assert has_keyword_fields
        assert has_geo_fields
        assert has_completion_fields
