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
    "callback",  # JSONP callback
    # Facet filter parameters (fq[aggregation_name][])
    "fq[resource_class_agg][]",
    "fq[resource_type_agg][]",
    "fq[spatial_agg][]",
    "fq[issued_agg][]",
    "fq[index_year_agg][]",
    "fq[language_agg][]",
    "fq[creator_agg][]",
    "fq[provider_agg][]",
    "fq[access_rights_agg][]",
    "fq[georeferenced_agg][]",
    "fq[id_agg][]",
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
