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
    # Facet filter parameters (allow any fq[field] or fq[field][]) via wildcard
    "fq[*]",
    # New dynamic filter params: include_filters[field][]=... & exclude_filters[field][]=...
    # We whitelist via wildcard markers consumed by strong_params
    "include_filters[*]",
    "exclude_filters[*]",
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
