"""
OGM Field Mapper Service

This service handles mapping between database column names (which are downcased)
and proper OGM Aardvark field names for BTAA flavored records.
"""

from typing import Any, Dict


class OGMFieldMapper:
    """
    Maps database column names to proper OGM Aardvark field names.

    The database downcases most element names as column names, so we get
    gbl_resourceclass_sm back from the database instead of gbl_resourceClass_sm.
    This mapper converts them back to the correct OGM field names.
    """

    # Mapping from database column names to proper OGM field names
    # Based on the BTAA OGM Aardvark schema
    FIELD_MAPPING = {
        # Standard OGM Aardvark fields
        "gbl_mdversion_s": "gbl_mdVersion_s",
        "gbl_mdmodified_dt": "gbl_mdModified_dt",
        "gbl_resourceclass_sm": "gbl_resourceClass_sm",
        "gbl_resourcetype_sm": "gbl_resourceType_sm",
        "gbl_indexyear_im": "gbl_indexYear_im",
        "gbl_daterange_drsim": "gbl_dateRange_drsim",
        "gbl_filesize_s": "gbl_fileSize_s",
        "gbl_wxsidentifier_s": "gbl_wxsIdentifier_s",
        "gbl_suppressed_b": "gbl_suppressed_b",
        "gbl_georeferenced_b": "gbl_georeferenced_b",
        "gbl_displaynote_sm": "gbl_displayNote_sm",
        # BTAA-specific fields (these may not exist in current DB but are in schema)
        "b1g_code_s": "b1g_code_s",
        "b1g_status_s": "b1g_status_s",
        "b1g_dct_accrualmethod_s": "b1g_dct_accrualMethod_s",
        "b1g_dct_accrualperiodicity_s": "b1g_dct_accrualPeriodicity_s",
        "b1g_dateaccessioned_s": "b1g_dateAccessioned_s",
        "b1g_dateretired_s": "b1g_dateRetired_s",
        "b1g_child_record_b": "b1g_child_record_b",
        "b1g_dct_mediator_sm": "b1g_dct_mediator_sm",
        "b1g_access_s": "b1g_access_s",
        "b1g_image_ss": "b1g_image_ss",
        "b1g_geonames_sm": "b1g_geonames_sm",
        "b1g_publication_state_s": "b1g_publication_state_s",
        "b1g_language_sm": "b1g_language_sm",
        "b1g_creatorid_sm": "b1g_creatorID_sm",
        "b1g_dct_conformsto_sm": "b1g_dct_conformsTo_sm",
        "b1g_dcat_spatialresolutioninmeters_sm": "b1g_dcat_spatialResolutionInMeters_sm",
        "b1g_geodcat_spatialresolutionastext_sm": "b1g_geodcat_spatialResolutionAsText_sm",
        "b1g_dct_provenancestatement_sm": "b1g_dct_provenanceStatement_sm",
        "b1g_admintags_sm": "b1g_adminTags_sm",
        # Other fields that might be downcased
        "dct_accessrights_s": "dct_accessRights_s",
        "dct_rightsholder_sm": "dct_rightsHolder_sm",
        "dct_ispartof_sm": "dct_isPartOf_sm",
        "dct_isversionof_sm": "dct_isVersionOf_sm",
        "dct_isreplacedby_sm": "dct_isReplacedBy_sm",
        "pcdm_memberof_sm": "pcdm_memberOf_sm",
        "layer_geom_type_s": "layer_geom_type_s",
        "solr_year_i": "solr_year_i",
        "layer_id_s": "layer_id_s",
        "suppressed_b": "suppressed_b",
    }

    @classmethod
    def map_resource_fields(cls, resource_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Maps database column names to proper OGM field names in a resource dictionary.

        Args:
            resource_dict: The resource data from the database

        Returns:
            Resource dictionary with proper OGM field names
        """
        mapped_dict = {}

        for db_field, value in resource_dict.items():
            # Map to proper OGM field name if it exists in our mapping
            ogm_field = cls.FIELD_MAPPING.get(db_field, db_field)
            mapped_dict[ogm_field] = value

        return mapped_dict

    @classmethod
    def get_required_fields(cls) -> list:
        """
        Returns the list of required fields according to the BTAA OGM Aardvark schema.

        Returns:
            List of required field names
        """
        return [
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

    @classmethod
    def get_all_schema_fields(cls) -> list:
        """
        Returns the list of all fields defined in the BTAA OGM Aardvark schema.

        Returns:
            List of all schema field names
        """
        return list(cls.FIELD_MAPPING.values()) + [
            # Fields that don't need mapping (already correct)
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

    @classmethod
    def get_ogm_aardvark_fields(cls) -> set:
        """
        Returns the set of all OGM Aardvark field names from the official schema.
        This is used to classify fields as OGM Aardvark vs B1G custom fields.

        Based on the OGM Aardvark JSON schema:
        https://opengeometadata.org/schema/geoblacklight-schema-aardvark.json

        Returns:
            Set of OGM Aardvark field names (including 'id' which appears both at
            root level per JSON:API and in ogm namespace)
        """
        return {
            # Standard OGM Aardvark fields from the schema
            "id",  # Required Aardvark field, also appears at root level per JSON:API
            "dct_title_s",
            "dct_alternative_sm",
            "dct_description_sm",
            "dct_language_sm",
            "gbl_displayNote_sm",
            "dct_creator_sm",
            "dct_publisher_sm",
            "schema_provider_s",
            "gbl_resourceClass_sm",
            "gbl_resourceType_sm",
            "dct_subject_sm",
            "dcat_theme_sm",
            "dcat_keyword_sm",
            "dct_temporal_sm",
            "dct_issued_s",
            "gbl_indexYear_im",
            "gbl_dateRange_drsim",
            "dct_spatial_sm",
            "locn_geometry",
            "dcat_bbox",
            "dcat_centroid",
            "dct_relation_sm",
            "pcdm_memberOf_sm",
            "dct_isPartOf_sm",
            "dct_source_sm",
            "dct_isVersionOf_sm",
            "dct_replaces_sm",
            "dct_isReplacedBy_sm",
            "dct_rights_sm",
            "dct_rightsHolder_sm",
            "dct_license_sm",
            "dct_accessRights_s",
            "dct_format_s",
            "gbl_fileSize_s",
            "gbl_wxsIdentifier_s",
            "dct_references_s",
            "dct_identifier_sm",
            "gbl_mdModified_dt",
            "gbl_mdVersion_s",
            "gbl_suppressed_b",
            "gbl_georeferenced_b",
        }
