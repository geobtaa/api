"""
Strong parameters configuration for FastAPI endpoints.
Defines whitelisted query parameters for each endpoint type to prevent
mass assignment vulnerabilities.
"""

# Search endpoint allowed parameters
SEARCH_ALLOWED_PARAMS = [
    "q",  # Search query
    "page",  # Page number
    "per_page",  # Results per page
    "sort",  # Sort option
    "search_field",  # Restrict search to specific ES fields
    "adv_q",  # Advanced multi-field search queries
    "fields",  # Field filtering for response attributes
    "facets",  # Facet filtering for response aggregations
    "meta",  # Include per-resource meta
    "callback",  # JSONP callback
    # Explicit facet filter parameters (fq[<field>][]) expected by tests
    "fq[dct_resourceClass_sm][]",
    "fq[gbl_resourceType_sm][]",
    "fq[dct_spatial_sm][]",
    "fq[gbl_indexYear_im][]",
    "fq[dct_language_sm][]",
    "fq[b1g_language_sm][]",
    "fq[dct_creator_sm][]",
    "fq[dct_publisher_sm][]",
    "fq[schema_provider_s][]",
    "fq[b1g_code_s][]",
    "fq[dct_accessRights_s][]",
    "fq[gbl_georeferenced_b][]",
    # Spatial facets
    "fq[geo_country][]",
    "fq[geo_region][]",
    "fq[geo_county][]",
    # Dynamic include/exclude filters (placeholder notation for validation/docs)
    "include_filters[field][]",
    "exclude_filters[field][]",
    # Convenience multi-select repo filter (OGM)
    "ogm_repo[]",
]

# Facet endpoint allowed parameters
FACET_ALLOWED_PARAMS = [
    "q",  # Search query to filter resultset
    "page",  # Page number
    "per_page",  # Facet values per page
    "sort",  # Sort option (count_desc, count_asc, alpha_asc, alpha_desc)
    "q_facet",  # Search query to filter facet values
    "adv_q",  # Advanced multi-field search queries
    "callback",  # JSONP callback
    # Explicit facet filter parameters (fq[<field>][]) expected by tests
    "fq[dct_resourceClass_sm][]",
    "fq[gbl_resourceType_sm][]",
    "fq[dct_spatial_sm][]",
    "fq[gbl_indexYear_im][]",
    "fq[dct_language_sm][]",
    "fq[b1g_language_sm][]",
    "fq[dct_creator_sm][]",
    "fq[dct_publisher_sm][]",
    "fq[schema_provider_s][]",
    "fq[b1g_code_s][]",
    "fq[dct_accessRights_s][]",
    "fq[gbl_georeferenced_b][]",
    # Spatial facets
    "fq[geo_country][]",
    "fq[geo_region][]",
    "fq[geo_county][]",
    # Dynamic include/exclude filters (placeholder notation for validation/docs)
    "include_filters[field][]",
    "exclude_filters[field][]",
    # Convenience multi-select repo filter (OGM)
    "ogm_repo[]",
]

# Gazetteer endpoint allowed parameters
GAZETTEER_ALLOWED_PARAMS = [
    "q",  # Search query
    "limit",  # Maximum results
    "offset",  # Results to skip
    "callback",  # JSONP callback
]

# Resource endpoint allowed parameters
RESOURCE_ALLOWED_PARAMS = [
    "callback",  # JSONP callback
]

# Admin endpoint allowed parameters
ADMIN_ALLOWED_PARAMS = [
    "callback",  # JSONP callback
]

# MCP endpoint allowed parameters
MCP_ALLOWED_PARAMS = [
    "callback",  # JSONP callback
]

# Shapefile endpoint allowed parameters
SHAPEFILE_ALLOWED_PARAMS = [
    "callback",  # JSONP callback
]

# Thumbnail endpoint allowed parameters
THUMBNAIL_ALLOWED_PARAMS = [
    "callback",  # JSONP callback
]
