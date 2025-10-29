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
    "fq[dct_creator_sm][]",
    "fq[schema_provider_s][]",
    "fq[dct_accessRights_s][]",
    "fq[gbl_georeferenced_b][]",
    # Spatial facets
    "fq[geo_country][]",
    "fq[geo_region][]",
    "fq[geo_county][]",
    # Dynamic include/exclude filters (placeholder notation for validation/docs)
    "include_filters[field][]",
    "exclude_filters[field][]",
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
