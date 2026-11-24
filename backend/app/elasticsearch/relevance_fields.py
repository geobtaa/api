"""Shared mapping/query fields for catalog relevance."""

SEARCH_FIELD_WEIGHTS = {
    "dct_title_s": 3,
    "dct_alternative_sm": 2,
    "dct_description_sm": 2,
    "summary": 2,
    "dct_creator_sm": 2,
    "dct_subject_sm": 1.5,
    "dcat_keyword_sm": 1.5,
    "dct_publisher_sm": 1,
    "schema_provider_s": 1,
    "dct_spatial_sm": 1,
    "gbl_displaynote_sm": 1,
    "dcat_theme_sm": 1,
    "gbl_resourceClass_sm": 1,
    "gbl_resourceType_sm": 1,
    "b1g_localCollectionLabel_sm": 1,
    "collection_titles": 1,
}
