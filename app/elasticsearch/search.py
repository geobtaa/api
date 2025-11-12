import json
import logging
import os
import time
from typing import Optional
from urllib.parse import urlencode

from dotenv import load_dotenv
from elasticsearch.exceptions import NotFoundError
from fastapi import HTTPException
from sqlalchemy.sql import text

from app.services.distribution_repository import fetch_distribution_context_map
from app.services.viewer_service import create_viewer_attributes  # Updated import
from db.database import database
from db.models import resources

from .client import es

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)

# Facet size configuration
GEO_COUNTRY_FACET_SIZE = int(os.getenv("GEO_COUNTRY_FACET_SIZE", "20"))
GEO_REGION_FACET_SIZE = int(os.getenv("GEO_REGION_FACET_SIZE", "50"))
GEO_COUNTY_FACET_SIZE = int(os.getenv("GEO_COUNTY_FACET_SIZE", "100"))
DEFAULT_FACET_SIZE = int(os.getenv("DEFAULT_FACET_SIZE", "10"))

# Fields that should use their `.keyword` subfield for aggregations and filters
KEYWORD_FILTER_FIELDS = {
    "dct_spatial_sm",
    "gbl_resourceClass_sm",
    "gbl_resourceType_sm",
    "dct_language_sm",
    "dct_creator_sm",
    "schema_provider_s",
    "dct_accessRights_s",
}


def _resolve_filter_field(field: str) -> str:
    """Return the appropriate ES field for filtering."""
    if field in KEYWORD_FILTER_FIELDS:
        return f"{field}.keyword"
    return field


def get_facet_aggregation_config(facet_name: str) -> dict:
    """Get Elasticsearch aggregation configuration for a given facet name.

    Args:
        facet_name: The facet field name (e.g., 'dct_spatial_sm', 'schema_provider_s')

    Returns:
        Dictionary with aggregation configuration including field and size

    Raises:
        ValueError: If facet_name is not a valid facet field
    """
    # Map facet names to their aggregation configurations
    facet_configs = {
        "dct_spatial_sm": {
            "field": "dct_spatial_sm.keyword",
            "size": DEFAULT_FACET_SIZE,
        },
        "gbl_resourceClass_sm": {
            "field": "gbl_resourceClass_sm.keyword",
            "size": DEFAULT_FACET_SIZE,
        },
        "gbl_resourceType_sm": {
            "field": "gbl_resourceType_sm.keyword",
            "size": DEFAULT_FACET_SIZE,
        },
        "gbl_indexYear_im": {
            "field": "gbl_indexYear_im",
            "size": DEFAULT_FACET_SIZE,
        },
        "dct_language_sm": {
            "field": "dct_language_sm.keyword",
            "size": DEFAULT_FACET_SIZE,
        },
        "dct_creator_sm": {
            "field": "dct_creator_sm.keyword",
            "size": DEFAULT_FACET_SIZE,
        },
        "schema_provider_s": {
            "field": "schema_provider_s.keyword",
            "size": DEFAULT_FACET_SIZE,
        },
        "dct_accessRights_s": {
            "field": "dct_accessRights_s.keyword",
            "size": DEFAULT_FACET_SIZE,
        },
        "gbl_georeferenced_b": {
            "field": "gbl_georeferenced_b",
            "size": DEFAULT_FACET_SIZE,
        },
        "geo_country": {
            "field": "geo_country",
            "size": GEO_COUNTRY_FACET_SIZE,
        },
        "geo_region": {
            "field": "geo_region",
            "size": GEO_REGION_FACET_SIZE,
        },
        "geo_county": {
            "field": "geo_county",
            "size": GEO_COUNTY_FACET_SIZE,
        },
    }

    if facet_name not in facet_configs:
        raise ValueError(f"Invalid facet name: {facet_name}")

    return facet_configs[facet_name]


def get_search_criteria(query: str, fq: dict, skip: int, limit: int, sort: list = None):
    """Return the currently applied search criteria."""
    return {
        "query": query,
        "filters": fq,
        "pagination": {"skip": skip, "limit": limit},
        "sort": sort or [{"_score": "desc"}],
    }


def _normalize_geo_params(geo_params: dict) -> dict:
    """Normalize flattened bracket keys into nested geo params structure.

    Examples of flattened keys this handles:
    - center][lat, center][lon
    - top_left][lat, bottom_right][lon
    - points][0][lat, points][1][lon
    - shape][type, shape][coordinates][0][0]
    """
    if not isinstance(geo_params, dict):
        return {}

    normalized: dict = {}

    def ensure_dict(parent: dict, key: str) -> dict:
        if key not in parent or not isinstance(parent[key], dict):
            parent[key] = {}
        return parent[key]

    def ensure_list(parent: dict, key: str, size: int) -> list:
        if key not in parent or not isinstance(parent[key], list):
            parent[key] = []
        lst = parent[key]
        while len(lst) <= size:
            lst.append(None)
        return lst

    def coerce_numeric(val):
        try:
            return float(val) if val is not None else None
        except (TypeError, ValueError):
            return val

    for raw_key, raw_value in geo_params.items():
        # Handle already structured payloads (e.g., POST body)
        if raw_key in {"type", "field", "distance", "relation"}:
            if isinstance(raw_value, list) and raw_value:
                normalized[raw_key] = raw_value[0]
            else:
                normalized[raw_key] = raw_value
            continue

        if raw_key in {"center", "top_left", "bottom_right"} and isinstance(raw_value, dict):
            normalized[raw_key] = {
                coord_key: coerce_numeric(coord_val) for coord_key, coord_val in raw_value.items()
            }
            continue

        if raw_key == "points" and isinstance(raw_value, list):
            points_list = []
            for point in raw_value:
                if isinstance(point, dict):
                    points_list.append(
                        {
                            coord_key: coerce_numeric(coord_val)
                            for coord_key, coord_val in point.items()
                        }
                    )
            if points_list:
                normalized["points"] = points_list
            continue

        if raw_key == "shape" and isinstance(raw_value, dict):
            normalized["shape"] = raw_value
            continue

        # Values may come as lists from parse_qs; take the first where appropriate
        value = raw_value[0] if isinstance(raw_value, list) and raw_value else raw_value

        # Tokenize keys like 'center][lat' or 'points][0][lat' or 'shape][coordinates][0][0]'
        tokens = raw_key.replace("][", "|").replace("[", "|").replace("]", "").split("|")
        tokens = [t for t in tokens if t]
        if not tokens:
            continue

        head = tokens[0]

        if head in {"center", "top_left", "bottom_right"}:
            target = ensure_dict(normalized, head)
            if len(tokens) >= 2 and tokens[1] in {"lat", "lon"}:
                try:
                    target[tokens[1]] = float(value) if value is not None else None
                except (TypeError, ValueError):
                    target[tokens[1]] = value
            continue

        if head == "points":
            if len(tokens) >= 3 and tokens[1].isdigit():
                idx = int(tokens[1])
                lst = ensure_list(normalized, "points", idx)
                if lst[idx] is None or not isinstance(lst[idx], dict):
                    lst[idx] = {}
                key = tokens[2]
                try:
                    lst[idx][key] = float(value) if value is not None else None
                except (TypeError, ValueError):
                    lst[idx][key] = value
            continue

        if head == "shape":
            shape_dict = ensure_dict(normalized, "shape")
            if len(tokens) >= 2 and tokens[1] == "type":
                shape_dict["type"] = value
                continue
            if len(tokens) >= 2 and tokens[1] == "coordinates":
                # coordinates might be e.g. [0][0] and [1][1]
                if len(tokens) >= 4 and tokens[2].isdigit() and tokens[3].isdigit():
                    outer_idx = int(tokens[2])
                    inner_idx = int(tokens[3])
                    # Ensure 2D list
                    if "coordinates" not in shape_dict or not isinstance(
                        shape_dict.get("coordinates"), list
                    ):
                        shape_dict["coordinates"] = []
                    coords = shape_dict["coordinates"]
                    while len(coords) <= outer_idx:
                        coords.append([])
                    while len(coords[outer_idx]) <= inner_idx:
                        coords[outer_idx].append(None)
                    try:
                        coords[outer_idx][inner_idx] = float(value) if value is not None else None
                    except (TypeError, ValueError):
                        coords[outer_idx][inner_idx] = value
                continue

    return normalized or geo_params


def _build_advanced_query(adv_q: list) -> dict:
    """Build Elasticsearch bool query from advanced query clauses.

    Args:
        adv_q: List of query clause dicts with keys: op, f, q

    Returns:
        Dict with must, should, must_not lists for bool query
    """
    must_clauses = []
    should_clauses = []
    must_not_clauses = []

    for clause in adv_q:
        # Extract op, f, q from clause
        operator = clause.get("op")
        field = clause.get("f")
        query = clause.get("q")

        # Normalize operator to uppercase
        if operator:
            operator = operator.upper()

        # Check if query is a phrase (wrapped in quotes)
        is_phrase = len(query) >= 2 and query.startswith('"') and query.endswith('"')
        phrase = query[1:-1] if is_phrase else query

        # Build match query for the field
        # Use simple match query - Elasticsearch will handle both analyzed and keyword fields
        match_query = {"match": {field: {"query": phrase, "operator": "and"}}}

        # Route to appropriate clause list based on operator
        if operator == "AND":
            must_clauses.append(match_query)
        elif operator == "OR":
            should_clauses.append(match_query)
        elif operator == "NOT":
            must_not_clauses.append(match_query)

    return {
        "must": must_clauses,
        "should": should_clauses,
        "must_not": must_not_clauses,
    }


def _build_geospatial_filter(geo_params: dict) -> dict | None:
    """Build Elasticsearch geospatial filter from geo parameters.

    Supports:
    - bbox: bounding box with top_left and bottom_right coordinates
    - distance: radius search with center point and distance
    - polygon: polygon search with array of points
    - shape: shape search with relation and shape definition
    """
    if not isinstance(geo_params, dict):
        return None

    # Normalize any flattened keys into nested structures
    geo_params = _normalize_geo_params(geo_params)

    geo_type = geo_params.get("type")
    geo_field = geo_params.get("field", "dcat_centroid")

    if geo_type == "bbox":
        top_left = geo_params.get("top_left", {})
        bottom_right = geo_params.get("bottom_right", {})

        if not all(
            [
                top_left.get("lat"),
                top_left.get("lon"),
                bottom_right.get("lat"),
                bottom_right.get("lon"),
            ]
        ):
            logger.warning("Invalid bbox parameters: missing lat/lon coordinates")
            return None

        return {
            "geo_bounding_box": {
                geo_field: {
                    "top_left": {"lat": float(top_left["lat"]), "lon": float(top_left["lon"])},
                    "bottom_right": {
                        "lat": float(bottom_right["lat"]),
                        "lon": float(bottom_right["lon"]),
                    },
                }
            }
        }

    elif geo_type == "distance":
        center = geo_params.get("center", {})
        distance = geo_params.get("distance", "10km")

        if not all([center.get("lat"), center.get("lon")]):
            logger.warning("Invalid distance parameters: missing center coordinates")
            return None

        return {
            "geo_distance": {
                "distance": distance,
                geo_field: {"lat": float(center["lat"]), "lon": float(center["lon"])},
            }
        }

    elif geo_type == "polygon":
        points = geo_params.get("points", [])

        if not points or len(points) < 3:
            logger.warning("Invalid polygon parameters: need at least 3 points")
            return None

        # Convert points to Elasticsearch polygon format (lon/lat order)
        coordinates = []
        for point in points:
            if not all([point.get("lat"), point.get("lon")]):
                logger.warning("Invalid polygon point: missing lat/lon")
                return None
            coordinates.append([float(point["lon"]), float(point["lat"])])

        # Close the polygon by adding the first point at the end
        if coordinates[0] != coordinates[-1]:
            coordinates.append(coordinates[0])

        relation = str(geo_params.get("relation", "intersects")).lower()
        allowed_relations = {"intersects", "within", "contains", "disjoint"}
        if relation not in allowed_relations:
            relation = "intersects"

        return {
            "geo_shape": {
                geo_field: {
                    "relation": relation,
                    "shape": {
                        "type": "polygon",
                        "coordinates": [coordinates],
                    },
                }
            }
        }

    elif geo_type == "shape":
        relation = geo_params.get("relation", "intersects")
        shape = geo_params.get("shape", {})

        if not shape:
            logger.warning("Invalid shape parameters: missing shape definition")
            return None

        shape_type = shape.get("type")
        coordinates = shape.get("coordinates", [])

        if shape_type == "envelope" and len(coordinates) == 2:
            # Convert envelope coordinates to proper format
            envelope_coords = [
                [float(coordinates[0][0]), float(coordinates[0][1])],  # top_left
                [float(coordinates[1][0]), float(coordinates[1][1])],  # bottom_right
            ]

            return {
                "geo_shape": {
                    geo_field: {
                        "shape": {"type": "envelope", "coordinates": envelope_coords},
                        "relation": relation,
                    }
                }
            }
        else:
            logger.warning(f"Unsupported shape type: {shape_type}")
            return None

    else:
        logger.warning(f"Unsupported geo type: {geo_type}")
        return None


async def search_resources(
    query: str = None,
    fq: dict = None,
    skip: int = 0,
    limit: int = 20,
    sort: list = None,
    search_fields: str | None = None,
    include_filters: dict | None = None,
    exclude_filters: dict | None = None,
    facets: Optional[str] = None,
    adv_q: Optional[list] = None,
):
    """Search resources in Elasticsearch with optional filters, sorting, and spelling
    suggestions."""
    # Ensure limit is not zero to avoid division by zero errors
    if limit <= 0:
        limit = 20  # Default to 20 if limit is zero or negative

    index_name = os.getenv("ELASTICSEARCH_INDEX", "btaa_geospatial_api")

    try:
        # Get the current search criteria
        search_criteria = get_search_criteria(query, fq, skip, limit, sort)
        logger.debug(f"Search criteria: {search_criteria}")

        # Construct the filter query (legacy fq + new include/exclude)
        filter_clauses = []
        must_not_clauses = []
        if fq:
            for field, values in fq.items():
                logger.debug(f"Processing filter - Field: {field}, Values: {values}")
                if isinstance(values, list):
                    filter_clauses.append({"terms": {field: values}})
                else:
                    filter_clauses.append({"term": {field: values}})

        if include_filters:
            for field, values in include_filters.items():
                resolved_field = _resolve_filter_field(field)

                # Handle geospatial queries
                if field == "geo" and isinstance(values, dict):
                    geo_filter = _build_geospatial_filter(values)
                    if geo_filter:
                        filter_clauses.append(geo_filter)
                elif isinstance(values, list):
                    # Use terms_set to ensure all specified values must be present
                    # when the field is an array
                    filter_clauses.append(
                        {
                            "terms_set": {
                                resolved_field: {
                                    "terms": values,
                                    "minimum_should_match_script": {"source": "params.num_terms"},
                                }
                            }
                        }
                    )
                else:
                    filter_clauses.append({"term": {resolved_field: values}})

        if exclude_filters:
            for field, values in exclude_filters.items():
                resolved_field = _resolve_filter_field(field)

                if isinstance(values, list):
                    must_not_clauses.append({"terms": {resolved_field: values}})
                else:
                    must_not_clauses.append({"term": {resolved_field: values}})

        # Optionally filter which aggs to include
        allowed_aggs = None
        if facets:
            allowed_aggs = {f.strip() for f in facets.split(",") if f.strip()}

        full_aggs = {
            "dct_spatial_sm": {
                "terms": {"field": "dct_spatial_sm.keyword", "size": DEFAULT_FACET_SIZE}
            },
            "gbl_resourceClass_sm": {
                "terms": {"field": "gbl_resourceClass_sm.keyword", "size": DEFAULT_FACET_SIZE}
            },
            "gbl_resourceType_sm": {
                "terms": {"field": "gbl_resourceType_sm.keyword", "size": DEFAULT_FACET_SIZE}
            },
            "gbl_indexYear_im": {
                "terms": {"field": "gbl_indexYear_im", "size": DEFAULT_FACET_SIZE}
            },
            "dct_language_sm": {
                "terms": {"field": "dct_language_sm.keyword", "size": DEFAULT_FACET_SIZE}
            },
            "dct_creator_sm": {
                "terms": {"field": "dct_creator_sm.keyword", "size": DEFAULT_FACET_SIZE}
            },
            "schema_provider_s": {
                "terms": {"field": "schema_provider_s.keyword", "size": DEFAULT_FACET_SIZE}
            },
            "dct_accessRights_s": {
                "terms": {"field": "dct_accessRights_s.keyword", "size": DEFAULT_FACET_SIZE}
            },
            "gbl_georeferenced_b": {
                "terms": {"field": "gbl_georeferenced_b", "size": DEFAULT_FACET_SIZE}
            },
            # Spatial facet aggregations with configurable sizes
            "geo_country": {"terms": {"field": "geo_country", "size": GEO_COUNTRY_FACET_SIZE}},
            "geo_region": {"terms": {"field": "geo_region", "size": GEO_REGION_FACET_SIZE}},
            "geo_county": {"terms": {"field": "geo_county", "size": GEO_COUNTY_FACET_SIZE}},
        }

        selected_aggs = (
            {k: v for k, v in full_aggs.items() if k in allowed_aggs} if allowed_aggs else full_aggs
        )

        # Build the search query
        # Support both q and adv_q simultaneously
        must_clauses = []
        should_clauses = []
        combined_must_not = list(must_not_clauses)

        # Build query from q parameter if provided
        if search_criteria.get("query"):
            query_text = search_criteria["query"] or ""
            is_phrase = (
                len(query_text) >= 2 and query_text.startswith('"') and query_text.endswith('"')
            )
            phrase = query_text[1:-1] if is_phrase else query_text

            # If specific fields are requested (and not 'all_fields'),
            # use multi_match across provided fields
            scoped = bool(search_fields) and search_fields.strip().lower() != "all_fields"
            if scoped:
                requested_fields = [f.strip() for f in search_fields.split(",") if f.strip()]
                # Prefer exact matches via .keyword when available,
                # but also search the analyzed field
                expanded_fields = []
                for f in requested_fields:
                    expanded_fields.append(f)
                    expanded_fields.append(f"{f}.keyword")

                must_clauses.append(
                    {
                        "multi_match": {
                            "query": phrase,
                            "type": "best_fields" if not is_phrase else "phrase",
                            "operator": "AND",
                            "fields": expanded_fields,
                        }
                    }
                )
            else:
                # Default behavior across boosted fields using query_string
                must_clauses.append(
                    {
                        "query_string": {
                            "query": query_text,
                            "fields": [
                                "id^5",
                                "dct_title_s^3",
                                "dct_description_sm^2",
                                "summary^2",
                                "dct_creator_sm^2",
                                "dct_subject_sm^1.5",
                                "dcat_keyword_sm^1.5",
                                "dct_publisher_sm",
                                "schema_provider_s",
                                "dct_spatial_sm",
                                "gbl_displaynote_sm",
                            ],
                            "default_operator": "AND",
                            "analyze_wildcard": True,
                            "allow_leading_wildcard": True,
                        }
                    }
                )

        # Build advanced query clauses if provided
        if adv_q:
            advanced_query_structure = _build_advanced_query(adv_q)
            # Add advanced query AND clauses to must
            must_clauses.extend(advanced_query_structure["must"])
            # Add advanced query OR clauses to should
            should_clauses.extend(advanced_query_structure["should"])
            # Add advanced query NOT clauses to must_not
            combined_must_not.extend(advanced_query_structure["must_not"])

        # Build the bool query combining all clauses
        bool_query_dict = {
            "filter": filter_clauses,
        }

        if must_clauses:
            bool_query_dict["must"] = must_clauses
        elif not should_clauses:
            # If no must clauses and no should clauses, match all
            bool_query_dict["must"] = [{"match_all": {}}]

        if should_clauses:
            bool_query_dict["should"] = should_clauses
            bool_query_dict["minimum_should_match"] = 1

        if combined_must_not:
            bool_query_dict["must_not"] = combined_must_not

        base_query = {"query": {"bool": bool_query_dict}}

        search_query = {
            **base_query,
            "from": skip,
            "size": limit,
            "sort": sort or [{"_score": "desc"}],
            "track_total_hits": True,
            "aggs": selected_aggs,
        }

        # Add suggestions if q parameter was provided
        if search_criteria.get("query") and search_criteria["query"].strip():
            search_query["suggest"] = {
                "text": search_criteria["query"],
                "simple_phrase": {
                    "phrase": {
                        "field": "dct_title_s",
                        "size": 1,
                        "gram_size": 3,
                        "direct_generator": [
                            {"field": "dct_title_s", "suggest_mode": "always"},
                            {"field": "dct_description_sm", "suggest_mode": "always"},
                        ],
                        "highlight": {"pre_tag": "<em>", "post_tag": "</em>"},
                    }
                },
            }

        # If neither q nor adv_q provided, search_query already has match_all in must

        logger.debug(f"ES Query: {json.dumps(search_query, indent=2)}")

        try:
            # Call ES using keyword args so tests can inspect 'query' and 'suggest'
            response = await es.search(
                index=index_name,
                query=search_query["query"],
                from_=skip,
                size=limit,
                sort=sort or [{"_score": "desc"}],
                track_total_hits=True,
                aggs=search_query["aggs"],
                suggest=search_query.get("suggest"),
            )
            response_dict = response.body if hasattr(response, "body") else response
        except NotFoundError:
            # Index missing: return empty result structure instead of 500
            logger.warning(f"Elasticsearch index '{index_name}' not found; returning empty results")
            empty_response = {
                "hits": {"total": {"value": 0}, "hits": []},
                "took": 0,
                "aggregations": {},
            }
            return await process_search_response(empty_response, limit, skip, search_criteria)
        except Exception as es_error:
            logger.error(f"Elasticsearch error: {str(es_error)}", exc_info=True)
            error_detail = {
                "message": "Elasticsearch query failed",
                "error": str(es_error),
                "query": search_query,
                "index": index_name,
            }
            if hasattr(es_error, "info"):
                error_detail["info"] = es_error.info
            if hasattr(es_error, "status_code"):
                error_detail["status_code"] = es_error.status_code
            raise HTTPException(status_code=500, detail=error_detail) from es_error

        return await process_search_response(response_dict, limit, skip, search_criteria)

    except Exception as e:
        logger.error(f"Search documents error: {str(e)}", exc_info=True)
        raise


def get_sort_options(search_criteria):
    """Generate sort options for the response."""
    base_url = os.getenv("APPLICATION_URL") + "/api/v1/search"
    current_params = {"q": search_criteria["query"] or "", "search_field": "all_fields"}

    # Add any existing filters to the params
    if search_criteria["filters"]:
        for field, values in search_criteria["filters"].items():
            if isinstance(values, list):
                for value in values:
                    current_params[f"fq[{field}][]"] = value
            else:
                current_params[f"fq[{field}][]"] = values

    sort_options = [
        {
            "type": "sort",
            "id": "relevance",
            "attributes": {"label": "Relevance"},
            "links": {
                "self": (
                    f"{base_url}?{urlencode({**current_params, 'sort': 'relevance'}, doseq=True)}"
                )
            },
        },
        {
            "type": "sort",
            "id": "year_desc",
            "attributes": {"label": "Year (Newest first)"},
            "links": {
                "self": (
                    f"{base_url}?{urlencode({**current_params, 'sort': 'year_desc'}, doseq=True)}"
                )
            },
        },
        {
            "type": "sort",
            "id": "year_asc",
            "attributes": {"label": "Year (Oldest first)"},
            "links": {
                "self": (
                    f"{base_url}?{urlencode({**current_params, 'sort': 'year_asc'}, doseq=True)}"
                )
            },
        },
        {
            "type": "sort",
            "id": "title_asc",
            "attributes": {"label": "Title (A-Z)"},
            "links": {
                "self": (
                    f"{base_url}?{urlencode({**current_params, 'sort': 'title_asc'}, doseq=True)}"
                )
            },
        },
        {
            "type": "sort",
            "id": "title_desc",
            "attributes": {"label": "Title (Z-A)"},
            "links": {
                "self": (
                    f"{base_url}?{urlencode({**current_params, 'sort': 'title_desc'}, doseq=True)}"
                )
            },
        },
    ]
    return sort_options


async def process_search_response(response, limit, skip, search_criteria):
    """Process Elasticsearch response and format for API output."""
    try:
        total_hits = response["hits"]["total"]["value"]
        logger.debug(f"Total hits: {total_hits}")

        document_ids = [hit["_source"]["id"] for hit in response["hits"]["hits"]]
        logger.debug(f"Found document IDs: {document_ids}")

        # Process spelling suggestions
        suggestions = []
        if "suggest" in response:
            simple_phrase = response["suggest"].get("simple_phrase", [])
            for suggestion in simple_phrase:
                if suggestion.get("options"):
                    for option in suggestion["options"]:
                        suggestions.append(
                            {
                                "text": option.get("text"),
                                "highlighted": option.get("highlighted"),
                                "score": option.get("score"),
                            }
                        )

        if not document_ids:
            logger.debug("No documents found")
            return {
                "status": "success",
                "query_time": {
                    "elasticsearch": response["took"].__str__() + "ms",
                    "postgresql": "0ms",
                },
                "meta": {
                    "pages": {
                        "current_page": (skip // limit) + 1,
                        "next_page": None,
                        "prev_page": (skip // limit) if skip > 0 else None,
                        "total_pages": 0,
                        "limit_value": limit,
                        "offset_value": skip,
                        "total_count": total_hits,
                        "first_page?": True,
                        "last_page?": True,
                    },
                    "suggestions": suggestions,  # Add suggestions to meta
                },
                "data": [],
                "included": [],
            }

        start_time = time.time()
        # Create a CASE statement to preserve the order of document_ids
        order_case = (
            "CASE "
            + " ".join(
                f"WHEN id = '{doc_id}' THEN {index}" for index, doc_id in enumerate(document_ids)
            )
            + " END"
        )

        query = (
            resources.select().where(resources.c.id.in_(document_ids)).order_by(text(order_case))
        )

        resource_rows = await database.fetch_all(query)
        processed_resources = []

        distribution_contexts = await fetch_distribution_context_map(
            [resource["id"] for resource in resource_rows]
        )

        for resource in resource_rows:
            distribution_context = distribution_contexts.get(resource["id"])
            processed_resources.append(
                {
                    "type": "document",
                    "id": resource["id"],
                    "score": next(
                        hit["_score"]
                        for hit in response["hits"]["hits"]
                        if hit["_source"]["id"] == resource["id"]
                    ),
                    "attributes": {
                        **resource,
                        **create_viewer_attributes(
                            resource, distribution_context=distribution_context
                        ),
                    },
                }
            )

        pg_query_time = (time.time() - start_time) * 1000

        included = [
            *process_aggregations(response.get("aggregations", {}), search_criteria),
            *get_sort_options(search_criteria),
        ]

        return {
            "status": "success",
            "query_time": {
                "elasticsearch": response["took"].__str__() + "ms",
                "postgresql": f"{round(pg_query_time)}ms",
            },
            "meta": {
                "pages": {
                    "current_page": (skip // limit) + 1,
                    "next_page": ((skip // limit) + 2) if (skip + limit) < total_hits else None,
                    "prev_page": (skip // limit) if skip > 0 else None,
                    "total_pages": (
                        (total_hits // limit) + (1 if total_hits % limit > 0 else 0)
                        if limit > 0
                        else 0
                    ),
                    "limit_value": limit,
                    "offset_value": skip,
                    "total_count": total_hits,
                    "first_page?": (skip == 0),
                    "last_page?": (skip + limit) >= total_hits,
                },
                "suggestions": suggestions,  # Add suggestions to meta
            },
            "data": processed_resources,
            "included": included,
        }

    except Exception as e:
        import traceback

        error_trace = traceback.format_exc()
        logger.error(f"Process response error: {str(e)}", exc_info=True)
        logger.error(f"Full traceback:\n{error_trace}")
        logger.error(f"Response body: {response}")
        raise HTTPException(
            status_code=500,
            detail={"error": str(e), "traceback": error_trace, "response": response},
        ) from e


def process_aggregations(aggregations, search_criteria):
    """Transform Elasticsearch aggregations into JSON:API includes."""
    # Define custom labels for aggregations
    agg_labels = {
        "id_agg": "ID",
        "spatial_agg": "Spatial Coverage",
        "resource_class_agg": "Resource Class",
        "resource_type_agg": "Resource Type",
        "index_year_agg": "Index Year",
        "language_agg": "Language",
        "creator_agg": "Creator",
        "provider_agg": "Provider",
        "access_rights_agg": "Access Rights",
        "georeferenced_agg": "Georeferenced",
        "geo_country_agg": "Country",
        "geo_region_agg": "Region",
        "geo_county_agg": "County",
    }

    return [
        {
            "type": "facet",
            "id": agg_name,
            "attributes": {
                "label": agg_labels.get(
                    agg_name, agg_name.replace("_sm", "").replace("_", " ").title()
                ),
                "items": [
                    {
                        "attributes": {
                            "label": bucket["key"],
                            "value": bucket["key"],
                            "hits": bucket["doc_count"],
                        },
                        "links": {
                            "self": generate_facet_link(agg_name, bucket["key"], search_criteria)
                        },
                    }
                    for bucket in agg_data["buckets"]
                ],
            },
        }
        for agg_name, agg_data in aggregations.items()
    ]


def generate_facet_link(agg_name, facet_value, search_criteria):
    """Generate a link for a facet with current search parameters.

    Uses include_filters format for consistency with the new search endpoint.
    """
    from urllib.parse import urlencode

    base_url = os.getenv("APPLICATION_URL", "http://localhost:8000") + "/api/v1/search"
    query_params = {
        "q": search_criteria["query"] or "",
    }

    # Add existing filters using include_filters format
    if search_criteria.get("filters"):
        for key, values in search_criteria["filters"].items():
            # Convert ES field names back to facet names (remove .keyword suffix if present)
            facet_key = key.replace(".keyword", "")
            if isinstance(values, list):
                for value in values:
                    query_params.setdefault(f"include_filters[{facet_key}][]", []).append(value)
            else:
                query_params.setdefault(f"include_filters[{facet_key}][]", []).append(values)

    # Add the new facet filter
    # Remove .keyword suffix if present for consistency
    facet_key = agg_name.replace(".keyword", "")
    query_params.setdefault(f"include_filters[{facet_key}][]", []).append(facet_value)

    query_string = urlencode(query_params, doseq=True)
    return f"{base_url}?{query_string}"


async def get_facet_values(
    facet_name: str,
    query: str = None,
    fq: dict = None,
    include_filters: dict | None = None,
    exclude_filters: dict | None = None,
    adv_q: Optional[list] = None,
    q_facet: Optional[str] = None,
    size: int = 1000,
):
    """Get facet values for a specific facet field within a search context.

    Args:
        facet_name: The facet field name (e.g., 'dct_spatial_sm', 'schema_provider_s')
        query: Search query string
        fq: Legacy filter queries dict
        include_filters: Include filters dict
        exclude_filters: Exclude filters dict
        adv_q: Advanced query clauses
        q_facet: Optional search query to filter facet values (client-side filtering)
        size: Maximum number of facet values to retrieve from ES (default: 1000)

    Returns:
        Raw Elasticsearch aggregation buckets

    Raises:
        ValueError: If facet_name is invalid
        HTTPException: If Elasticsearch query fails
    """
    index_name = os.getenv("ELASTICSEARCH_INDEX", "btaa_geospatial_api")

    # Get facet aggregation configuration
    facet_config = get_facet_aggregation_config(facet_name)
    agg_field = facet_config["field"]

    # Build the same filter query structure as search_resources
    filter_clauses = []
    must_not_clauses = []

    if fq:
        for field, values in fq.items():
            if isinstance(values, list):
                filter_clauses.append({"terms": {field: values}})
            else:
                filter_clauses.append({"term": {field: values}})

    if include_filters:
        for field, values in include_filters.items():
            resolved_field = _resolve_filter_field(field)

            # Handle geospatial queries
            if field == "geo" and isinstance(values, dict):
                geo_filter = _build_geospatial_filter(values)
                if geo_filter:
                    filter_clauses.append(geo_filter)
            elif isinstance(values, list):
                filter_clauses.append(
                    {
                        "terms_set": {
                            resolved_field: {
                                "terms": values,
                                "minimum_should_match_script": {"source": "params.num_terms"},
                            }
                        }
                    }
                )
            else:
                filter_clauses.append({"term": {resolved_field: values}})

    if exclude_filters:
        for field, values in exclude_filters.items():
            resolved_field = _resolve_filter_field(field)
            if isinstance(values, list):
                must_not_clauses.append({"terms": {resolved_field: values}})
            else:
                must_not_clauses.append({"term": {resolved_field: values}})

    # Build query clauses (same as search_resources)
    must_clauses = []
    should_clauses = []
    combined_must_not = list(must_not_clauses)

    # Build query from q parameter if provided
    if query:
        query_text = query or ""
        # Note: is_phrase and phrase are calculated for consistency with search_resources,
        # but query_string handles quotes natively, so we use query_text directly
        is_phrase = len(query_text) >= 2 and query_text.startswith('"') and query_text.endswith('"')
        _phrase = query_text[1:-1] if is_phrase else query_text  # Unused but kept for consistency

        must_clauses.append(
            {
                "query_string": {
                    "query": query_text,
                    "fields": [
                        "id^5",
                        "dct_title_s^3",
                        "dct_description_sm^2",
                        "summary^2",
                        "dct_creator_sm^2",
                        "dct_subject_sm^1.5",
                        "dcat_keyword_sm^1.5",
                        "dct_publisher_sm",
                        "schema_provider_s",
                        "dct_spatial_sm",
                        "gbl_displaynote_sm",
                    ],
                    "default_operator": "AND",
                    "analyze_wildcard": True,
                    "allow_leading_wildcard": True,
                }
            }
        )

    # Build advanced query clauses if provided
    if adv_q:
        advanced_query_structure = _build_advanced_query(adv_q)
        must_clauses.extend(advanced_query_structure["must"])
        should_clauses.extend(advanced_query_structure["should"])
        combined_must_not.extend(advanced_query_structure["must_not"])

    # Build the bool query
    bool_query_dict = {"filter": filter_clauses}

    if must_clauses:
        bool_query_dict["must"] = must_clauses
    elif not should_clauses:
        bool_query_dict["must"] = [{"match_all": {}}]

    if should_clauses:
        bool_query_dict["should"] = should_clauses
        bool_query_dict["minimum_should_match"] = 1

    if combined_must_not:
        bool_query_dict["must_not"] = combined_must_not

    # Build aggregation with large size to get all values for sorting/filtering
    agg_config = {"terms": {"field": agg_field, "size": size}}

    # Optionally use ES include parameter for filtering (but we'll do client-side for simplicity)
    if q_facet:
        # Use regex pattern matching in ES for better performance on large datasets
        # Escape special regex characters
        import re

        escaped_query = re.escape(q_facet)
        agg_config["terms"]["include"] = f".*{escaped_query}.*"

    search_query = {
        "query": {"bool": bool_query_dict},
        "size": 0,  # We only want aggregations, not documents
        "aggs": {"facet_values": agg_config},
    }

    try:
        response = await es.search(
            index=index_name,
            query=search_query["query"],
            size=0,
            aggs=search_query["aggs"],
        )
        response_dict = response.body if hasattr(response, "body") else response
        return response_dict.get("aggregations", {}).get("facet_values", {}).get("buckets", [])
    except Exception as es_error:
        logger.error(f"Elasticsearch error getting facet values: {str(es_error)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(es_error)) from es_error


def process_facet_response(
    buckets: list,
    facet_name: str,
    search_criteria: dict,
    page: int = 1,
    per_page: int = 10,
    sort: str = "count_desc",
    q_facet: Optional[str] = None,
) -> dict:
    """Process and format facet aggregation buckets into paginated JSON:API response.

    Args:
        buckets: Raw aggregation buckets from Elasticsearch
        facet_name: The facet field name
        search_criteria: Search criteria dict (for generating links)
        page: Page number (1-based)
        per_page: Items per page
        sort: Sort option ('count_desc', 'count_asc', 'alpha_asc', 'alpha_desc')
        q_facet: Optional search query to filter facet values

    Returns:
        Dictionary with processed facet data ready for JSON:API formatting
    """
    # Apply client-side filtering if q_facet provided (case-insensitive)
    filtered_buckets = buckets
    if q_facet:
        q_facet_lower = q_facet.lower()
        filtered_buckets = [
            bucket for bucket in buckets if q_facet_lower in str(bucket.get("key", "")).lower()
        ]

    # Sort buckets based on sort parameter
    if sort == "count_desc":
        filtered_buckets = sorted(
            filtered_buckets, key=lambda x: x.get("doc_count", 0), reverse=True
        )
    elif sort == "count_asc":
        filtered_buckets = sorted(
            filtered_buckets, key=lambda x: x.get("doc_count", 0), reverse=False
        )
    elif sort == "alpha_asc":
        filtered_buckets = sorted(
            filtered_buckets, key=lambda x: str(x.get("key", "")).lower(), reverse=False
        )
    elif sort == "alpha_desc":
        filtered_buckets = sorted(
            filtered_buckets, key=lambda x: str(x.get("key", "")).lower(), reverse=True
        )
    else:
        # Default to count_desc
        filtered_buckets = sorted(
            filtered_buckets, key=lambda x: x.get("doc_count", 0), reverse=True
        )

    # Calculate pagination
    total_count = len(filtered_buckets)
    total_pages = max(1, (total_count + per_page - 1) // per_page) if per_page > 0 else 1
    skip = (page - 1) * per_page
    paginated_buckets = filtered_buckets[skip : skip + per_page]

    # Format facet values as JSON:API resources
    facet_items = []
    for bucket in paginated_buckets:
        facet_value = bucket.get("key", "")
        doc_count = bucket.get("doc_count", 0)

        # Generate link for this facet value
        facet_link = generate_facet_link(facet_name, facet_value, search_criteria)

        facet_items.append(
            {
                "type": "facet_value",
                "id": str(facet_value),
                "attributes": {
                    "label": str(facet_value),
                    "value": str(facet_value),
                    "hits": doc_count,
                },
                "links": {
                    "self": facet_link,
                },
            }
        )

    return {
        "data": facet_items,
        "meta": {
            "totalCount": total_count,
            "totalPages": total_pages,
            "currentPage": page,
            "perPage": per_page,
            "facetName": facet_name,
            "sort": sort,
        },
    }
