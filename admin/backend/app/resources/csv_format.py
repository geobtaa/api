"""GEOMGv1 primary column names, in the supplied export's order.

Administrative columns are accepted as source evidence, never Resource mutations.
"""

PRIMARY = {
    "Title": "dct_title_s",
    "Alternative Title": "dct_alternative_sm",
    "Description": "dct_description_sm",
    "Display Note": "gbl_displayNote_sm",
    "Creator": "dct_creator_sm",
    "Creator ID": "b1g_creatorID_sm",
    "Publisher": "dct_publisher_sm",
    "Provider": "schema_provider_s",
    "Resource Class": "gbl_resourceClass_sm",
    "Resource Type": "gbl_resourceType_sm",
    "Subject": "dct_subject_sm",
    "Theme": "dcat_theme_sm",
    "Keyword": "dcat_keyword_sm",
    "Language": "dct_language_sm",
    "B1G Language": "b1g_language_sm",
    "Local Collection": "b1g_localCollectionLabel_sm",
    "Temporal Coverage": "dct_temporal_sm",
    "Date Issued": "dct_issued_s",
    "Index Year": "gbl_indexYear_im",
    "Date Range": "gbl_dateRange_drsim",
    "Spatial Coverage": "dct_spatial_sm",
    "Bounding Box": "dcat_bbox",
    "Geometry": "locn_geometry",
    "Centroid": "dcat_centroid",
    "GeoNames": "b1g_geonames_sm",
    "Coordinate Reference System": "b1g_dct_conformsTo_sm",
    "Spatial Resolution in Meters": "b1g_dcat_spatialResolutionInMeters_sm",
    "Spatial Resolution as Text": "b1g_geodcat_spatialResolutionAsText_sm",
    "Georeferenced": "gbl_georeferenced_b",
    "Provenance": "b1g_dct_provenance_sm",
    "Format": "dct_format_s",
    "File Size": "gbl_fileSize_s",
    "B1G Image": "b1g_image_ss",
    "Member Of": "pcdm_memberOf_sm",
    "Is Part Of": "dct_isPartOf_sm",
    "Source": "dct_source_sm",
    "Is Version Of": "dct_isVersionOf_sm",
    "Replaces": "dct_replaces_sm",
    "Is Replaced By": "dct_isReplacedBy_sm",
    "Relation": "dct_relation_sm",
    "Rights": "dct_rights_sm",
    "License": "dct_license_sm",
    "Rights Holder": "dct_rightsHolder_sm",
    "Access Rights": "dct_accessRights_s",
    "ID": "id",
    "Identifier": "dct_identifier_sm",
    "WxS Identifier": "gbl_wxsIdentifier_s",
}
EVIDENCE = {
    "Publication State",
    "Website Platform",
    "Endpoint URL",
    "Endpoint Description",
    "Is Harvested",
    "Last Harvested",
    "Accrual Method",
    "Accrual Periodicity",
    "Harvest Workflow",
    "Created At",
    "Updated At",
    "Date Accessioned",
    "Date Retired",
    "Suppressed Record",
    "Deprioritized",
    "Mediator",
    "Access",
    "Code",
    "Tags",
    "Admin Note",
}
EXTRA = {
    "Source ID": "source_id",
    "Metadata Version": "gbl_mdVersion_s",
    "Provenance Statement": "b1g_dct_provenanceStatement_sm",
    "Legacy Spatial Resolution": "b1g_dcat_spatialResolutionInMeters_s",
    "Set ID": "set_id",
    "Lock Version": "lock_version",
    "Distributions": "distributions",
    "CSV Encoding": "_csv_encoding",
}
ALIASES = PRIMARY | EXTRA
LABELS = {name: label for label, name in ALIASES.items()}


def field_name(label):
    if label.endswith("__clear"):
        return ALIASES.get(label[:-7], label[:-7]) + "__clear"
    return ALIASES.get(label, LEGACY_PUBLICATION_FIELDS.get(label, label))


# These GEOMGv1 columns describe administration at the time of export.
LEGACY_PUBLICATION_FIELDS = {
    "b1g_code_s": "Code",
    "b1g_dateAccessioned_s": "Date Accessioned",
    "b1g_dct_accrualMethod_s": "Accrual Method",
    "b1g_publication_state_s": "Publication State",
}


def validate_header(header, template, *, friendly):
    """Require a complete current template or a complete GBL Admin primary export."""
    present = set(header)
    legacy = set(PRIMARY.values()) | EVIDENCE
    missing_template = set(template) - present
    missing_legacy = legacy - present
    if not missing_template or not missing_legacy:
        return
    if present & EVIDENCE:
        missing, format_name = missing_legacy, "GBL Admin export"
    else:
        missing, format_name = missing_template, "Resource CSV template"
    labels = sorted(LABELS.get(name, name) if friendly else name for name in missing)
    raise ValueError(f"Incomplete {format_name}. Missing columns: {', '.join(labels)}.")


def crosswalk(columns):
    legacy = {label: name for name, label in LEGACY_PUBLICATION_FIELDS.items()}
    rules = {
        "id": "Required Resource ID for create and update",
        "dct_title_s": "Required title. An empty Title cell is invalid",
        "lock_version": "Checks for edits since export. Leave blank to use the version at preview.",
        "set_id": "Optional assertion of the managing Set",
        "source_id": "Optional assertion of the managing Set's Source",
        "gbl_mdVersion_s": "Defaults to Aardvark on create. Blank clears the version on update",
        "_csv_encoding": "Keep this marker when editing an exported file",
        "distributions": "Ordered JSON list. A blank cell removes all links on update",
    }
    for label in columns:
        name = field_name(label)
        rule = rules.get(name, "Editable metadata. A blank cell clears the value on update")
        yield label, name, rule
    for label in sorted(EVIDENCE):
        yield (
            label,
            legacy.get(label, ""),
            "Historical upload evidence. Current administration uses separate staff commands.",
        )
