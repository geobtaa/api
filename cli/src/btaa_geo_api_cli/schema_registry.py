FACET_FIELDS = [
    "gbl_resourceClass_sm",
    "gbl_resourceType_sm",
    "dct_spatial_sm",
    "gbl_indexYear_im",
    "dct_language_sm",
    "b1g_language_sm",
    "dct_creator_sm",
    "dct_publisher_sm",
    "schema_provider_s",
    "b1g_code_s",
    "dct_accessRights_s",
    "gbl_georeferenced_b",
    "geo_country",
    "geo_region",
    "geo_county",
    "ogm_repo",
    "dct_isPartOf_sm",
    "pcdm_memberOf_sm",
    "b1g_localCollectionLabel_sm",
]

SEARCH_FIELDS = [
    "all_fields",
    "dct_title_s",
    "dct_description_sm",
    "dct_subject_sm",
    "dct_creator_sm",
    "dct_publisher_sm",
    "dct_spatial_sm",
    "schema_provider_s",
]

SEARCH_PARAMS = [
    "q",
    "page",
    "per_page",
    "sort",
    "search_field",
    "fields",
    "facets",
    "meta",
    "adv_q",
    "include_filters[field][]",
    "exclude_filters[field][]",
]

SORTS = ["relevance", "year_desc", "year_asc", "title_asc", "title_desc"]
