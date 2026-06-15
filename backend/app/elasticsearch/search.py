import json
import logging
import math
import os
import re
import time
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlencode

from dotenv import load_dotenv
from elasticsearch.exceptions import NotFoundError
from fastapi import HTTPException
from sqlalchemy.sql import text

from app.services.cache_service import ENDPOINT_CACHE, CacheService
from app.services.distribution_repository import fetch_distribution_context_map
from app.services.viewer_service import create_viewer_attributes  # Updated import
from db.database import database
from db.models import resources

from .client import es

# Load environment variables from .env file
try:
    load_dotenv()
except (OSError, PermissionError):
    # In sandboxed environments, .env may be unreadable. Continue with defaults/env.
    pass

logger = logging.getLogger(__name__)

# Facet size configuration
GEO_COUNTRY_FACET_SIZE = int(os.getenv("GEO_COUNTRY_FACET_SIZE", "20"))
GEO_REGION_FACET_SIZE = int(os.getenv("GEO_REGION_FACET_SIZE", "50"))
GEO_COUNTY_FACET_SIZE = int(os.getenv("GEO_COUNTY_FACET_SIZE", "100"))
OGM_REPO_FACET_SIZE = int(os.getenv("OGM_REPO_FACET_SIZE", "200"))
DEFAULT_FACET_SIZE = int(os.getenv("DEFAULT_FACET_SIZE", "11"))
NEAR_GLOBAL_DIAGONAL_KM = 15_000
MIN_BBOX_IOU_OVERLAP_RATIO = float(os.getenv("MIN_BBOX_IOU_OVERLAP_RATIO", "0.001"))
ALLOWED_GEO_RELATIONS = {"intersects", "within", "contains", "disjoint"}
GEO_MIN_LON = -180.0
GEO_MAX_LON = 180.0
GEO_MIN_LAT = -90.0
GEO_MAX_LAT = 90.0
BBOX_CONTAINMENT_WEIGHT = float(os.getenv("BBOX_CONTAINMENT_WEIGHT", "0.7"))
BBOX_IOU_WEIGHT = float(os.getenv("BBOX_IOU_WEIGHT", "0.3"))
BBOX_SPATIAL_BOOST_WEIGHT = float(os.getenv("BBOX_SPATIAL_BOOST_WEIGHT", "0.8"))
SEARCH_FACET_CACHE_TTL = int(os.getenv("SEARCH_FACET_CACHE_TTL", "3600"))
SEARCH_TIMING_LOG_THRESHOLD_MS = float(os.getenv("SEARCH_TIMING_LOG_THRESHOLD_MS", "750"))
SEARCH_FACET_CACHE_NAMESPACE = "search.facets"
FACET_VALUES_CACHE_NAMESPACE = "search.facet_values"


def _escape_query_string_brackets(query_text: str) -> str:
    """Escape literal characters that frequently break identifier searches.

    query_string treats [] and {} as special syntax (ranges/expressions), and a colon
    inside tokens is interpreted as fielded-query syntax. That breaks common resource
    identifiers like ``p16022coll244:471`` unless we escape the literal colon.
    """
    if not query_text:
        return query_text
    return (
        query_text.replace("\\", r"\\")
        .replace("[", r"\[")
        .replace("]", r"\]")
        .replace("{", r"\{")
        .replace("}", r"\}")
        .replace(":", r"\:")
    )


def _build_case_insensitive_facet_regex(query_text: str) -> str:
    """Build a Lucene regex that matches facet values case-insensitively.

    Facet autocomplete aggregates over keyword fields, and the ``terms.include``
    regex is case-sensitive. Expand alphabetic characters into explicit
    lower/upper character classes so values like ``Michigan`` still match a
    lowercase ``michigan`` query before Elasticsearch trims the bucket list.
    """
    pattern_parts: list[str] = []

    for char in query_text:
        lower = char.lower()
        upper = char.upper()

        if char.isalpha() and len(lower) == 1 and len(upper) == 1 and lower != upper:
            pattern_parts.append(f"[{re.escape(lower)}{re.escape(upper)}]")
        else:
            pattern_parts.append(re.escape(char))

    return f".*{''.join(pattern_parts)}.*"


# Fields that should use their `.keyword` subfield for aggregations and filters
# Note: geo_country, geo_region, geo_county are already keyword fields, so they don't need .keyword
KEYWORD_FILTER_FIELDS = {
    "dct_spatial_sm",
    "gbl_resourceClass_sm",
    "gbl_resourceType_sm",
    "dct_language_sm",
    "dct_creator_sm",
    "schema_provider_s",
    "dct_accessRights_s",
    "dct_subject_sm",
    "dct_publisher_sm",
    "dcat_theme_sm",
    "dcat_keyword_sm",
    "time_period",  # Auto-mapped as text with keyword subfield
    "ogm_repo",
    "dct_isPartOf_sm",  # Relationship filter (has part / is part of)
    "pcdm_memberOf_sm",  # Relationship filter (collection records / member of)
    "b1g_localCollectionLabel_sm",  # Local collection facet
}

DIRECT_FILTER_FIELDS = {
    # BTAA code is mapped as a keyword already, so filters should target the field directly.
    "b1g_code_s",
    "b1g_language_sm",
}


def _resolve_filter_field(field: str) -> str:
    """Return the appropriate ES field for filtering."""
    if field in DIRECT_FILTER_FIELDS:
        return field
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
            "size": 6,
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
        "time_period": {
            "field": "time_period.keyword",
            "size": DEFAULT_FACET_SIZE,
        },
        "dct_language_sm": {
            "field": "dct_language_sm.keyword",
            "size": DEFAULT_FACET_SIZE,
        },
        "b1g_language_sm": {
            "field": "b1g_language_sm",
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
        "ogm_repo": {
            # ogm_repo is mapped as text with a keyword subfield (for aggs/filters)
            "field": "ogm_repo.keyword",
            "size": OGM_REPO_FACET_SIZE,
        },
        "dct_accessRights_s": {
            "field": "dct_accessRights_s.keyword",
            "size": DEFAULT_FACET_SIZE,
        },
        "gbl_georeferenced_b": {
            "field": "gbl_georeferenced_b",
            "size": DEFAULT_FACET_SIZE,
        },
        "b1g_georeferenced_allmaps_b": {
            "field": "b1g_georeferenced_allmaps_b",
            "size": DEFAULT_FACET_SIZE,
        },
        "dct_subject_sm": {
            "field": "dct_subject_sm.keyword",
            "size": DEFAULT_FACET_SIZE,
        },
        "dct_publisher_sm": {
            "field": "dct_publisher_sm.keyword",
            "size": DEFAULT_FACET_SIZE,
        },
        "dcat_theme_sm": {
            "field": "dcat_theme_sm.keyword",
            "size": DEFAULT_FACET_SIZE,
        },
        "dcat_keyword_sm": {
            "field": "dcat_keyword_sm.keyword",
            "size": DEFAULT_FACET_SIZE,
        },
        "b1g_code_s": {
            "field": "b1g_code_s",
            "size": DEFAULT_FACET_SIZE,
        },
        "b1g_localCollectionLabel_sm": {
            "field": "b1g_localCollectionLabel_sm.keyword",
            "size": DEFAULT_FACET_SIZE,
        },
        "geo_country": {
            "field": "geo_country.keyword",
            "size": GEO_COUNTRY_FACET_SIZE,
        },
        "geo_region": {
            "field": "geo_region.keyword",
            "size": GEO_REGION_FACET_SIZE,
        },
        "geo_county": {
            "field": "geo_county.keyword",
            "size": GEO_COUNTY_FACET_SIZE,
        },
    }

    if facet_name not in facet_configs:
        raise ValueError(f"Invalid facet name: {facet_name}")

    return facet_configs[facet_name]


def _global_bucket_aggregation() -> dict:
    """Return the shared map/global bucket aggregation.

    `geo_or_near_global` is precomputed at index time, so using it here avoids
    re-evaluating the same OR/range logic for every aggregation request.
    """
    return {"filter": {"term": {"geo_or_near_global": True}}}


def _build_search_aggregations() -> dict:
    """Return the default search aggregation set in response order."""
    return {
        "dct_spatial_sm": {
            "terms": {"field": "dct_spatial_sm.keyword", "size": DEFAULT_FACET_SIZE}
        },
        "gbl_resourceClass_sm": {
            "terms": {"field": "gbl_resourceClass_sm.keyword", "size": DEFAULT_FACET_SIZE}
        },
        "gbl_resourceType_sm": {
            "terms": {"field": "gbl_resourceType_sm.keyword", "size": DEFAULT_FACET_SIZE}
        },
        "gbl_indexYear_im": {"terms": {"field": "gbl_indexYear_im", "size": DEFAULT_FACET_SIZE}},
        "year_histogram": {
            "histogram": {
                "field": "gbl_indexYear_im",
                "interval": 1,
                "min_doc_count": 1,
            }
        },
        "time_period": {"terms": {"field": "time_period.keyword", "size": DEFAULT_FACET_SIZE}},
        "b1g_language_sm": {"terms": {"field": "b1g_language_sm", "size": DEFAULT_FACET_SIZE}},
        "dct_creator_sm": {
            "terms": {"field": "dct_creator_sm.keyword", "size": DEFAULT_FACET_SIZE}
        },
        "dct_publisher_sm": {
            "terms": {"field": "dct_publisher_sm.keyword", "size": DEFAULT_FACET_SIZE}
        },
        "schema_provider_s": {
            "terms": {"field": "schema_provider_s.keyword", "size": DEFAULT_FACET_SIZE}
        },
        "b1g_code_s": {"terms": {"field": "b1g_code_s", "size": DEFAULT_FACET_SIZE}},
        "ogm_repo": {"terms": {"field": "ogm_repo.keyword", "size": OGM_REPO_FACET_SIZE}},
        "dct_accessRights_s": {
            "terms": {"field": "dct_accessRights_s.keyword", "size": DEFAULT_FACET_SIZE}
        },
        "gbl_georeferenced_b": {
            "terms": {"field": "gbl_georeferenced_b", "size": DEFAULT_FACET_SIZE}
        },
        "b1g_georeferenced_allmaps_b": {
            "terms": {
                "field": "b1g_georeferenced_allmaps_b",
                "size": DEFAULT_FACET_SIZE,
            }
        },
        "geo_country": {"terms": {"field": "geo_country.keyword", "size": GEO_COUNTRY_FACET_SIZE}},
        "geo_region": {"terms": {"field": "geo_region.keyword", "size": GEO_REGION_FACET_SIZE}},
        "geo_county": {"terms": {"field": "geo_county.keyword", "size": GEO_COUNTY_FACET_SIZE}},
        "global_bucket_agg": _global_bucket_aggregation(),
    }


def _normalize_search_fields(search_fields: str | None) -> str:
    return (search_fields or "").strip()


def _build_search_facet_cache_key(
    *,
    index_name: str,
    query: str | None,
    search_fields: str | None,
    fq: dict | None,
    include_filters: dict | None,
    exclude_filters: dict | None,
    adv_q: Optional[list],
    selected_aggs: tuple[str, ...],
) -> str:
    return CacheService.generate_cache_key(
        SEARCH_FACET_CACHE_NAMESPACE,
        index=index_name,
        query=query or "",
        search_fields=_normalize_search_fields(search_fields),
        fq=fq or {},
        include_filters=include_filters or {},
        exclude_filters=exclude_filters or {},
        adv_q=adv_q or [],
        aggs=selected_aggs,
    )


def _build_facet_values_cache_key(
    *,
    index_name: str,
    facet_name: str,
    query: str | None,
    fq: dict | None,
    include_filters: dict | None,
    exclude_filters: dict | None,
    adv_q: Optional[list],
    q_facet: str | None,
    size: int,
) -> str:
    return CacheService.generate_cache_key(
        FACET_VALUES_CACHE_NAMESPACE,
        index=index_name,
        facet_name=facet_name,
        query=query or "",
        fq=fq or {},
        include_filters=include_filters or {},
        exclude_filters=exclude_filters or {},
        adv_q=adv_q or [],
        q_facet=q_facet or "",
        size=size,
    )


async def _get_cached_search_aggregations(cache_key: str) -> dict | None:
    if not ENDPOINT_CACHE:
        return None

    payload = await CacheService().get(cache_key)
    if not isinstance(payload, dict):
        return None

    aggregations = payload.get("aggregations")
    return aggregations if isinstance(aggregations, dict) else None


async def _store_cached_search_aggregations(
    cache_key: str, aggregations: dict, selected_aggs: tuple[str, ...]
) -> None:
    if not ENDPOINT_CACHE or not aggregations:
        return

    cache_service = CacheService()
    stored = await cache_service.set(
        cache_key,
        {
            "aggregations": aggregations,
        },
        ttl=SEARCH_FACET_CACHE_TTL,
    )
    if stored:
        await cache_service.tag_cache_key(
            cache_key,
            ["search", *(f"facet:{agg_name}" for agg_name in selected_aggs)],
            ttl_seconds=SEARCH_FACET_CACHE_TTL,
        )


async def _get_cached_facet_values(cache_key: str) -> list[dict] | None:
    if not ENDPOINT_CACHE:
        return None

    payload = await CacheService().get(cache_key)
    if not isinstance(payload, dict):
        return None

    buckets = payload.get("buckets")
    return buckets if isinstance(buckets, list) else None


async def _store_cached_facet_values(cache_key: str, facet_name: str, buckets: list[dict]) -> None:
    if not ENDPOINT_CACHE:
        return

    cache_service = CacheService()
    stored = await cache_service.set(
        cache_key,
        {
            "buckets": buckets,
        },
        ttl=SEARCH_FACET_CACHE_TTL,
    )
    if stored:
        await cache_service.tag_cache_key(
            cache_key,
            ["search", f"facet:{facet_name}"],
            ttl_seconds=SEARCH_FACET_CACHE_TTL,
        )


def _log_aggregation_timing(
    *,
    operation: str,
    cache_status: str,
    total_ms: float,
    es_roundtrip_ms: float,
    es_took_ms: float,
    cache_lookup_ms: float,
    cache_store_ms: float,
    aggregation_names: tuple[str, ...],
    total_hits: int | None = None,
    hit_count: int | None = None,
    source: str = "primary",
) -> None:
    payload = {
        "operation": operation,
        "source": source,
        "cacheStatus": cache_status,
        "totalMs": round(total_ms, 2),
        "esRoundtripMs": round(es_roundtrip_ms, 2),
        "esTookMs": round(es_took_ms, 2),
        "cacheLookupMs": round(cache_lookup_ms, 2),
        "cacheStoreMs": round(cache_store_ms, 2),
        "aggregationNames": list(aggregation_names),
    }
    if total_hits is not None:
        payload["totalHits"] = int(total_hits)
    if hit_count is not None:
        payload["hitCount"] = int(hit_count)

    log_message = "aggregation_timing %s"
    if total_ms >= SEARCH_TIMING_LOG_THRESHOLD_MS or cache_status != "hit":
        logger.info(log_message, json.dumps(payload, separators=(",", ":"), sort_keys=True))
    elif logger.isEnabledFor(logging.DEBUG):
        logger.debug(log_message, json.dumps(payload, separators=(",", ":"), sort_keys=True))


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


def _normalize_geo_relation(relation: str | None, default: str = "intersects") -> str:
    normalized = str(relation or default).lower()
    if normalized not in ALLOWED_GEO_RELATIONS:
        return default
    return normalized


def _normalize_longitude(longitude: float) -> float:
    normalized = ((longitude + 180.0) % 360.0) - 180.0
    if normalized == -180.0 and longitude > 0:
        return 180.0
    return normalized


def _normalize_geo_bbox_bounds(top_left: dict, bottom_right: dict) -> dict | None:
    """Return bounded bbox coordinates safe for Elasticsearch geo queries.

    Leaflet can report longitudes outside [-180, 180] when the map is panned into
    wrapped world copies. Elasticsearch rejects those coordinates, so normalize
    them here and split antimeridian-crossing ranges into two legal envelopes.
    """
    try:
        west_raw = float(top_left["lon"])
        east_raw = float(bottom_right["lon"])
        north_raw = float(top_left["lat"])
        south_raw = float(bottom_right["lat"])
    except (KeyError, TypeError, ValueError):
        logger.warning("Invalid bbox parameters: non-numeric lat/lon coordinates")
        return None

    if not all(math.isfinite(value) for value in (west_raw, east_raw, north_raw, south_raw)):
        logger.warning("Invalid bbox parameters: non-finite lat/lon coordinates")
        return None

    north = min(GEO_MAX_LAT, max(GEO_MIN_LAT, max(north_raw, south_raw)))
    south = min(GEO_MAX_LAT, max(GEO_MIN_LAT, min(north_raw, south_raw)))
    if north <= south:
        logger.warning("Invalid bbox parameters: zero-height latitude range")
        return None

    raw_lon_span = east_raw - west_raw
    if abs(raw_lon_span) >= 360.0:
        lon_ranges = [(GEO_MIN_LON, GEO_MAX_LON)]
    else:
        west = _normalize_longitude(west_raw)
        east = _normalize_longitude(east_raw)
        if west == east:
            if raw_lon_span == 0:
                logger.warning("Invalid bbox parameters: zero-width longitude range")
                return None
            lon_ranges = [(GEO_MIN_LON, GEO_MAX_LON)]
        elif west < east:
            lon_ranges = [(west, east)]
        elif (
            GEO_MIN_LON <= west_raw <= GEO_MAX_LON
            and GEO_MIN_LON <= east_raw <= GEO_MAX_LON
            and west - east <= 180.0
        ):
            lon_ranges = [(east, west)]
        else:
            lon_ranges = [(west, GEO_MAX_LON), (GEO_MIN_LON, east)]

    normalized_ranges = [
        (west, east)
        for west, east in lon_ranges
        if west >= GEO_MIN_LON and east <= GEO_MAX_LON and west < east
    ]
    if not normalized_ranges:
        logger.warning("Invalid bbox parameters: no searchable longitude range")
        return None

    return {
        "north": north,
        "south": south,
        "lon_ranges": normalized_ranges,
    }


def _normalize_min_overlap_ratio(raw: object) -> float:
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return MIN_BBOX_IOU_OVERLAP_RATIO
    if value < 0.0 or value > 1.0:
        return MIN_BBOX_IOU_OVERLAP_RATIO
    return value


def _normalized_spatial_weights() -> tuple[float, float]:
    containment_weight = max(0.0, BBOX_CONTAINMENT_WEIGHT)
    overlap_weight = max(0.0, BBOX_IOU_WEIGHT)
    total = containment_weight + overlap_weight
    if total <= 0.0:
        return 0.7, 0.3
    return containment_weight / total, overlap_weight / total


def _compute_bbox_spatial_metrics(
    *,
    d_minx: float,
    d_maxx: float,
    d_miny: float,
    d_maxy: float,
    q_minx: float,
    q_maxx: float,
    q_miny: float,
    q_maxy: float,
) -> dict[str, float]:
    ix1 = max(d_minx, q_minx)
    iy1 = max(d_miny, q_miny)
    ix2 = min(d_maxx, q_maxx)
    iy2 = min(d_maxy, q_maxy)

    iw = max(0.0, ix2 - ix1)
    ih = max(0.0, iy2 - iy1)
    intersection = iw * ih
    doc_area = max(0.0, (d_maxx - d_minx) * (d_maxy - d_miny))
    query_area = max(0.0, (q_maxx - q_minx) * (q_maxy - q_miny))

    if intersection <= 0.0 or doc_area <= 0.0 or query_area <= 0.0:
        return {
            "overlap_ratio": 0.0,
            "containment_ratio": 0.0,
            "spatial_score": 0.0,
        }

    union_area = doc_area + query_area - intersection
    overlap_ratio = 0.0 if union_area <= 0.0 else intersection / union_area
    containment_ratio = intersection / doc_area

    overlap_ratio = min(max(overlap_ratio, 0.0), 1.0)
    containment_ratio = min(max(containment_ratio, 0.0), 1.0)

    containment_weight, overlap_weight = _normalized_spatial_weights()
    spatial_score = containment_weight * containment_ratio + overlap_weight * overlap_ratio

    return {
        "overlap_ratio": overlap_ratio,
        "containment_ratio": containment_ratio,
        "spatial_score": min(max(spatial_score, 0.0), 1.0),
    }


def _build_bbox_overlap_filter(
    *,
    q_minx: float,
    q_maxx: float,
    q_miny: float,
    q_maxy: float,
    min_overlap_ratio: float,
) -> dict:
    """Filter out trivial bbox overlaps using IoU overlap ratio."""
    return {
        "script": {
            "script": {
                "source": """
                    if (doc['bbox_minx'].size() == 0 ||
                        doc['bbox_maxx'].size() == 0 ||
                        doc['bbox_miny'].size() == 0 ||
                        doc['bbox_maxy'].size() == 0) {
                        return false;
                    }
                    double dMinX;
                    double dMinY;
                    double dMaxX;
                    double dMaxY;
                    try {
                        dMinX = doc['bbox_minx'].value;
                        dMinY = doc['bbox_miny'].value;
                        dMaxX = doc['bbox_maxx'].value;
                        dMaxY = doc['bbox_maxy'].value;
                    } catch (Exception e) {
                        return false;
                    }

                    double qMinX = params.qMinX;
                    double qMaxX = params.qMaxX;
                    double qMinY = params.qMinY;
                    double qMaxY = params.qMaxY;

                    double ix1 = Math.max(dMinX, qMinX);
                    double iy1 = Math.max(dMinY, qMinY);
                    double ix2 = Math.min(dMaxX, qMaxX);
                    double iy2 = Math.min(dMaxY, qMaxY);

                    double iw = Math.max(0.0, ix2 - ix1);
                    double ih = Math.max(0.0, iy2 - iy1);
                    double intersection = iw * ih;
                    double docArea = Math.max(0.0, (dMaxX - dMinX) * (dMaxY - dMinY));
                    double queryArea = Math.max(0.0, (qMaxX - qMinX) * (qMaxY - qMinY));
                    if (intersection <= 0.0 || docArea <= 0.0 || queryArea <= 0.0) {
                        return false;
                    }

                    double unionArea = docArea + queryArea - intersection;
                    if (unionArea <= 0.0) {
                        return false;
                    }

                    double overlapRatio = intersection / unionArea;
                    return overlapRatio >= params.minOverlapRatio;
                """,
                "params": {
                    "qMinX": q_minx,
                    "qMaxX": q_maxx,
                    "qMinY": q_miny,
                    "qMaxY": q_maxy,
                    "minOverlapRatio": min_overlap_ratio,
                },
            }
        }
    }


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

    # Fields to search when "all_fields" is specified (same as regular q parameter)
    ALL_FIELDS_SEARCH_FIELDS = [
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
    ]

    # Check if there are any OR clauses
    has_or_clauses = any(
        clause.get("op", "").upper() == "OR" for clause in adv_q if clause.get("op")
    )

    # If there are OR clauses, check if all non-NOT clauses are on the same field
    # If so, treat them all as OR clauses (even if some are marked as AND)
    # This handles the case: [{"op":"AND","f":"field","q":"A"}, {"op":"OR","f":"field","q":"B"}]
    # which should be interpreted as: field contains A OR B
    treat_all_as_or = False
    if has_or_clauses:
        # Get all non-NOT clauses
        non_not_clauses = [clause for clause in adv_q if clause.get("op", "").upper() != "NOT"]
        if non_not_clauses:
            # Check if all non-NOT clauses are on the same field
            first_field = non_not_clauses[0].get("f")
            all_same_field = all(clause.get("f") == first_field for clause in non_not_clauses)
            # If all on same field, treat all non-NOT clauses as OR
            if all_same_field:
                treat_all_as_or = True

    for clause in adv_q:
        # Extract op, f, q from clause
        operator = clause.get("op")
        field = clause.get("f")
        query = clause.get("q")

        # Normalize operator to uppercase
        if operator:
            operator = operator.upper()

        # Build query based on field type
        if field and field.lower() in ("all_fields", "all", "*"):
            # For "all_fields", use query_string across multiple fields
            # (same as regular q parameter). query_string handles quotes natively,
            # so use the original query text
            query_clause = {
                "query_string": {
                    "query": _escape_query_string_brackets(query),
                    "fields": ALL_FIELDS_SEARCH_FIELDS,
                    "default_operator": "AND",
                    "analyze_wildcard": True,
                    "allow_leading_wildcard": True,
                }
            }
        else:
            # For specific fields, use match query
            # Check if query is a phrase (wrapped in quotes) and extract it
            is_phrase = len(query) >= 2 and query.startswith('"') and query.endswith('"')
            phrase = query[1:-1] if is_phrase else query
            # Use simple match query - Elasticsearch will handle both analyzed and keyword fields
            query_clause = {"match": {field: {"query": phrase, "operator": "and"}}}

        # Route to appropriate clause list based on operator
        # Special handling: if there are OR clauses and all non-NOT clauses are on the same field,
        # treat all non-NOT clauses as OR (even if marked as AND)
        if operator == "NOT":
            must_not_clauses.append(query_clause)
        elif treat_all_as_or:
            # If we're in "OR mode" (all same field with OR clauses), put everything in should
            should_clauses.append(query_clause)
        elif operator == "AND":
            must_clauses.append(query_clause)
        elif operator == "OR":
            should_clauses.append(query_clause)

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

    logger.debug("Normalized geo_params: %s", geo_params)

    geo_type = geo_params.get("type")
    geo_field = geo_params.get("field", "dcat_centroid")

    logger.debug("Geo filter - type: %s, field: %s", geo_type, geo_field)

    if geo_type == "bbox":
        top_left = geo_params.get("top_left", {})
        bottom_right = geo_params.get("bottom_right", {})

        if any(
            coord is None
            for coord in (
                top_left.get("lat"),
                top_left.get("lon"),
                bottom_right.get("lat"),
                bottom_right.get("lon"),
            )
        ):
            logger.warning("Invalid bbox parameters: missing lat/lon coordinates")
            return None

        bbox_bounds = _normalize_geo_bbox_bounds(top_left, bottom_right)
        if not bbox_bounds:
            return None

        north = bbox_bounds["north"]
        south = bbox_bounds["south"]
        lon_ranges = bbox_bounds["lon_ranges"]
        relation = _normalize_geo_relation(geo_params.get("relation"))

        # Use geo_shape query for geo_shape fields (dcat_bbox, locn_geometry)
        # Use geo_bounding_box for geo_point fields (dcat_centroid)
        if geo_field in ["dcat_bbox", "locn_geometry"]:
            geo_filters = []
            for west, east in lon_ranges:
                # Use envelope type for bounding boxes (more efficient than polygon).
                # Envelope format: [[west_lon, north_lat], [east_lon, south_lat]]
                envelope_coords = [
                    [west, north],
                    [east, south],
                ]

                geo_filters.append(
                    {
                        "geo_shape": {
                            geo_field: {
                                "shape": {
                                    "type": "envelope",
                                    "coordinates": envelope_coords,
                                },
                                "relation": relation,
                            }
                        }
                    }
                )

            geo_filter = (
                geo_filters[0]
                if len(geo_filters) == 1
                else {"bool": {"should": geo_filters, "minimum_should_match": 1}}
            )

            logger.debug("Geo filter for %s: %s", geo_field, geo_filter)
            return geo_filter
        else:
            # Use geo_bounding_box for geo_point fields (dcat_centroid)
            geo_filters = [
                {
                    "geo_bounding_box": {
                        geo_field: {
                            "top_left": {"lat": north, "lon": west},
                            "bottom_right": {"lat": south, "lon": east},
                        }
                    }
                }
                for west, east in lon_ranges
            ]
            return (
                geo_filters[0]
                if len(geo_filters) == 1
                else {"bool": {"should": geo_filters, "minimum_should_match": 1}}
            )

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

        relation = _normalize_geo_relation(geo_params.get("relation"))

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
        relation = _normalize_geo_relation(geo_params.get("relation"))
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


@dataclass
class SearchParams:
    """Normalized inputs for a resource search request."""

    query: str | None = None
    fq: dict | None = None
    skip: int = 0
    limit: int = 20
    sort: list | None = None
    search_fields: str | None = None
    include_filters: dict | None = None
    exclude_filters: dict | None = None
    facets: str | None = None
    adv_q: list | None = None
    hydrate_hits: bool = True
    index_name: str = ""

    @classmethod
    def from_inputs(
        cls,
        *,
        query: str | None,
        fq: dict | None,
        skip: int,
        limit: int,
        sort: list | None,
        search_fields: str | None,
        include_filters: dict | None,
        exclude_filters: dict | None,
        facets: str | None,
        adv_q: list | None,
        hydrate_hits: bool,
    ) -> "SearchParams":
        normalized_limit = limit if limit > 0 else 20
        return cls(
            query=query,
            fq=fq,
            skip=skip,
            limit=normalized_limit,
            sort=sort,
            search_fields=search_fields,
            include_filters=include_filters,
            exclude_filters=exclude_filters,
            facets=facets,
            adv_q=adv_q,
            hydrate_hits=hydrate_hits,
            index_name=os.getenv("ELASTICSEARCH_INDEX", "btaa_geospatial_api"),
        )

    @property
    def sort_clause(self) -> list:
        return self.sort or [{"_score": "desc"}]

    def criteria(self) -> dict:
        return get_search_criteria(self.query, self.fq, self.skip, self.limit, self.sort)


@dataclass
class SearchFacetSelection:
    aggregations: dict
    names: tuple[str, ...]
    cache_key: str | None = None
    cached_aggregations: dict | None = None
    cache_status: str = "disabled"
    cache_lookup_ms: float = 0.0
    cache_store_ms: float = 0.0


class FacetService:
    """Selects and caches search facet aggregations."""

    async def prepare(self, params: SearchParams, search_criteria: dict) -> SearchFacetSelection:
        allowed_aggs = None
        if params.facets:
            allowed_aggs = {f.strip() for f in params.facets.split(",") if f.strip()}

        full_aggs = _build_search_aggregations()
        selected_aggs = (
            {k: v for k, v in full_aggs.items() if k in allowed_aggs} if allowed_aggs else full_aggs
        )
        selected_agg_names = tuple(selected_aggs.keys())
        selection = SearchFacetSelection(
            aggregations=selected_aggs,
            names=selected_agg_names,
        )

        if not selected_aggs:
            return selection

        selection.cache_key = _build_search_facet_cache_key(
            index_name=params.index_name,
            query=search_criteria.get("query"),
            search_fields=params.search_fields,
            fq=params.fq,
            include_filters=params.include_filters,
            exclude_filters=params.exclude_filters,
            adv_q=params.adv_q,
            selected_aggs=selected_agg_names,
        )
        facet_cache_lookup_start = time.perf_counter()
        selection.cached_aggregations = await _get_cached_search_aggregations(selection.cache_key)
        selection.cache_lookup_ms = (time.perf_counter() - facet_cache_lookup_start) * 1000
        selection.cache_status = "hit" if selection.cached_aggregations is not None else "miss"
        return selection

    async def apply_to_response(
        self,
        response_dict: dict,
        selection: SearchFacetSelection,
    ) -> None:
        if selection.cached_aggregations is not None:
            response_dict["aggregations"] = selection.cached_aggregations
            return

        if not selection.cache_key or not selection.aggregations:
            return

        facet_cache_store_start = time.perf_counter()
        await _store_cached_search_aggregations(
            selection.cache_key,
            response_dict.get("aggregations", {}) or {},
            selection.names,
        )
        selection.cache_store_ms = (time.perf_counter() - facet_cache_store_start) * 1000


@dataclass
class SearchFilterPlan:
    filter_clauses: list
    must_not_clauses: list
    bbox_filter_info: dict | None = None


@dataclass
class SearchQueryPlan:
    search_query: dict
    bool_query: dict
    overlap_context: dict | None = None


class GeoFilterBuilder:
    """Builds geospatial filters and optional bbox scoring context."""

    def build(self, values: dict) -> tuple[dict | None, dict | None]:
        logger.debug("Building geo filter from values: %s", values)
        geo_filter = _build_geospatial_filter(values)
        if not geo_filter:
            logger.warning(f"Failed to build geo filter from values: {values}")
            return None, None

        logger.debug("Geo filter built successfully: %s", geo_filter)
        return geo_filter, self._bbox_filter_info(values)

    def _bbox_filter_info(self, values: dict) -> dict | None:
        if not (
            values.get("type") == "bbox" and values.get("top_left") and values.get("bottom_right")
        ):
            return None

        bbox_bounds = _normalize_geo_bbox_bounds(values["top_left"], values["bottom_right"])
        if bbox_bounds and len(bbox_bounds["lon_ranges"]) == 1:
            return {
                "bounds": bbox_bounds,
                "field": values.get("field", "dcat_centroid"),
                "min_overlap_ratio": values.get("min_overlap_ratio"),
            }
        return None


class SearchQueryBuilder:
    """Builds the Elasticsearch query body for resource search."""

    def __init__(
        self,
        params: SearchParams,
        search_criteria: dict,
        facet_selection: SearchFacetSelection,
    ):
        self.params = params
        self.search_criteria = search_criteria
        self.facet_selection = facet_selection
        self.geo_filter_builder = GeoFilterBuilder()

    def build(self) -> SearchQueryPlan:
        filter_plan = self._build_filters()
        must_clauses, should_clauses, combined_must_not = self._build_query_clauses(
            filter_plan.must_not_clauses
        )
        bool_query = self._build_bool_query(
            filter_plan.filter_clauses,
            must_clauses,
            should_clauses,
            combined_must_not,
        )
        base_query, overlap_context = self._build_base_query(
            bool_query,
            filter_plan.filter_clauses,
            filter_plan.bbox_filter_info,
        )

        search_query = {
            **base_query,
            "from": self.params.skip,
            "size": self.params.limit,
            "sort": self.params.sort_clause,
            "track_total_hits": True,
        }
        if self.facet_selection.cached_aggregations is None and self.facet_selection.aggregations:
            search_query["aggs"] = self.facet_selection.aggregations

        suggest = self._build_suggest()
        if suggest:
            search_query["suggest"] = suggest

        return SearchQueryPlan(
            search_query=search_query,
            bool_query=bool_query,
            overlap_context=overlap_context,
        )

    def _build_filters(self) -> SearchFilterPlan:
        filter_clauses = []
        must_not_clauses = []
        bbox_filter_info = None

        if self.params.fq:
            for field, values in self.params.fq.items():
                resolved_field = _resolve_filter_field(field)
                logger.debug(
                    f"Processing filter - Field: {field}, "
                    f"Resolved: {resolved_field}, Values: {values}"
                )
                if isinstance(values, list):
                    filter_clauses.append({"terms": {resolved_field: values}})
                else:
                    filter_clauses.append({"term": {resolved_field: values}})

        if self.params.include_filters:
            for field, values in self.params.include_filters.items():
                resolved_field = _resolve_filter_field(field)

                if field == "geo" and isinstance(values, dict):
                    geo_filter, geo_bbox_info = self.geo_filter_builder.build(values)
                    if geo_filter:
                        filter_clauses.append(geo_filter)
                        if geo_bbox_info:
                            bbox_filter_info = geo_bbox_info
                elif field == "year_range" and isinstance(values, dict):
                    year_range_filter = self._build_year_range_filter(values)
                    if year_range_filter:
                        filter_clauses.append(year_range_filter)
                elif field in ("geo_global", "geo_or_near_global") and isinstance(values, list):
                    if values and str(values[0]).lower() == "true":
                        filter_clauses.append({"term": {resolved_field: True}})
                elif isinstance(values, list):
                    filter_clauses.append({"terms": {resolved_field: values}})
                else:
                    filter_clauses.append({"term": {resolved_field: values}})

        if self.params.exclude_filters:
            for field, values in self.params.exclude_filters.items():
                resolved_field = _resolve_filter_field(field)

                if isinstance(values, list):
                    must_not_clauses.append({"terms": {resolved_field: values}})
                else:
                    must_not_clauses.append({"term": {resolved_field: values}})

        return SearchFilterPlan(
            filter_clauses=filter_clauses,
            must_not_clauses=must_not_clauses,
            bbox_filter_info=bbox_filter_info,
        )

    def _build_year_range_filter(self, values: dict) -> dict | None:
        year_range_filter = {"range": {"gbl_indexYear_im": {}}}
        if "start" in values:
            try:
                year_range_filter["range"]["gbl_indexYear_im"]["gte"] = int(values["start"])
            except (ValueError, TypeError):
                # Keep invalid year bounds permissive; ignore only the bad bound.
                logger.debug("Ignoring invalid start year filter value: %r", values["start"])
        if "end" in values:
            try:
                year_range_filter["range"]["gbl_indexYear_im"]["lte"] = int(values["end"])
            except (ValueError, TypeError):
                # Keep invalid year bounds permissive; ignore only the bad bound.
                logger.debug("Ignoring invalid end year filter value: %r", values["end"])

        if year_range_filter["range"]["gbl_indexYear_im"]:
            return year_range_filter
        return None

    def _build_query_clauses(self, must_not_clauses: list) -> tuple[list, list, list]:
        must_clauses = []
        should_clauses = []
        combined_must_not = list(must_not_clauses)

        query_value = self.search_criteria.get("query")
        if query_value and query_value.strip():
            must_clauses.append(self._build_text_query_clause(query_value.strip()))

        if self.params.adv_q:
            advanced_query_structure = _build_advanced_query(self.params.adv_q)
            must_clauses.extend(advanced_query_structure["must"])
            should_clauses.extend(advanced_query_structure["should"])
            combined_must_not.extend(advanced_query_structure["must_not"])

        return must_clauses, should_clauses, combined_must_not

    def _build_text_query_clause(self, query_text: str) -> dict:
        is_phrase = len(query_text) >= 2 and query_text.startswith('"') and query_text.endswith('"')
        phrase = query_text[1:-1] if is_phrase else query_text
        scoped = (
            bool(self.params.search_fields)
            and self.params.search_fields.strip().lower() != "all_fields"
        )

        if scoped:
            requested_fields = [
                f.strip() for f in self.params.search_fields.split(",") if f.strip()
            ]
            expanded_fields = []
            for field_name in requested_fields:
                expanded_fields.append(field_name)
                expanded_fields.append(f"{field_name}.keyword")

            return {
                "multi_match": {
                    "query": phrase,
                    "type": "best_fields" if not is_phrase else "phrase",
                    "operator": "AND",
                    "fields": expanded_fields,
                }
            }

        return {
            "query_string": {
                "query": _escape_query_string_brackets(query_text),
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

    def _build_bool_query(
        self,
        filter_clauses: list,
        must_clauses: list,
        should_clauses: list,
        combined_must_not: list,
    ) -> dict:
        bool_query = {}

        if filter_clauses:
            bool_query["filter"] = filter_clauses

        logger.debug("Bool query - filter clauses count: %s", len(filter_clauses))
        if filter_clauses:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug("Filter clauses: %s", json.dumps(filter_clauses, indent=2))
        else:
            logger.debug("No filter clauses found - query will return all results")

        if must_clauses:
            bool_query["must"] = must_clauses
        elif not should_clauses:
            bool_query["must"] = [{"match_all": {}}]

        if should_clauses:
            bool_query["should"] = should_clauses
            bool_query["minimum_should_match"] = 1

        if combined_must_not:
            bool_query["must_not"] = combined_must_not

        return bool_query

    def _build_base_query(
        self,
        bool_query: dict,
        filter_clauses: list,
        bbox_filter_info: dict | None,
    ) -> tuple[dict, dict | None]:
        base_query = {"query": {"bool": bool_query}}
        overlap_context = None

        if not bbox_filter_info:
            return base_query, overlap_context

        bbox_bounds = bbox_filter_info["bounds"]
        west, east = bbox_bounds["lon_ranges"][0]
        q_minx = west
        q_maxx = east
        q_miny = bbox_bounds["south"]
        q_maxy = bbox_bounds["north"]
        containment_weight, overlap_weight = _normalized_spatial_weights()

        overlap_context = {
            "qMinX": q_minx,
            "qMaxX": q_maxx,
            "qMinY": q_miny,
            "qMaxY": q_maxy,
        }
        min_overlap_ratio = _normalize_min_overlap_ratio(bbox_filter_info.get("min_overlap_ratio"))
        filter_clauses.append(
            _build_bbox_overlap_filter(
                q_minx=q_minx,
                q_maxx=q_maxx,
                q_miny=q_miny,
                q_maxy=q_maxy,
                min_overlap_ratio=min_overlap_ratio,
            )
        )

        return (
            {
                "query": {
                    "script_score": {
                        "query": {"bool": bool_query},
                        "script": {
                            "source": """
                                // Read document bbox from numeric bbox_* fields
                                if (doc['bbox_minx'].size() == 0 ||
                                    doc['bbox_maxx'].size() == 0 ||
                                    doc['bbox_miny'].size() == 0 ||
                                    doc['bbox_maxy'].size() == 0) {
                                    return _score;
                                }
                                double dMinX;
                                double dMinY;
                                double dMaxX;
                                double dMaxY;
                                try {
                                    dMinX = doc['bbox_minx'].value;
                                    dMinY = doc['bbox_miny'].value;
                                    dMaxX = doc['bbox_maxx'].value;
                                    dMaxY = doc['bbox_maxy'].value;
                                } catch (Exception e) {
                                    return _score;
                                }

                                // Query bbox
                                double qMinX = params.qMinX;
                                double qMaxX = params.qMaxX;
                                double qMinY = params.qMinY;
                                double qMaxY = params.qMaxY;

                                // Intersection bbox
                                double ix1 = Math.max(dMinX, qMinX);
                                double iy1 = Math.max(dMinY, qMinY);
                                double ix2 = Math.min(dMaxX, qMaxX);
                                double iy2 = Math.min(dMaxY, qMaxY);

                                double iw = Math.max(0.0, ix2 - ix1);
                                double ih = Math.max(0.0, iy2 - iy1);
                                double intersection = iw * ih;
                                double docArea = Math.max(0.0, (dMaxX - dMinX) * (dMaxY - dMinY));
                                double queryArea = Math.max(0.0, (qMaxX - qMinX) * (qMaxY - qMinY));

                                if (intersection <= 0.0 || docArea <= 0.0 || queryArea <= 0.0) {
                                    // If we can't establish a meaningful overlap,
                                    // push this document to the bottom of the
                                    // relevance ranking for bbox queries.
                                    return 0.0;
                                }

                                double unionArea = docArea + queryArea - intersection;
                                if (unionArea <= 0.0) {
                                    return 0.0;
                                }

                                // Prefer records whose mapped extent is mostly inside
                                // the user's view, while still rewarding similar extent.
                                double containmentRatio = intersection / docArea;
                                if (containmentRatio < 0.0) {
                                    containmentRatio = 0.0;
                                } else if (containmentRatio > 1.0) {
                                    containmentRatio = 1.0;
                                }

                                // Overlap similarity: IoU between document bbox and query bbox.
                                // This is high (near 1.0) only when the two extents are similar
                                // in both size and location.
                                double overlapRatio = intersection / unionArea;
                                if (overlapRatio < 0.0) {
                                    overlapRatio = 0.0;
                                } else if (overlapRatio > 1.0) {
                                    overlapRatio = 1.0;
                                }

                                double spatialScore =
                                    (params.containmentWeight * containmentRatio) +
                                    (params.overlapWeight * overlapRatio);

                                if (spatialScore < 0.0) {
                                    spatialScore = 0.0;
                                } else if (spatialScore > 1.0) {
                                    spatialScore = 1.0;
                                }

                                // Combine base text relevance with a spatial boost.
                                double baseScore = _score;
                                return baseScore * (
                                    1.0 + (params.spatialBoostWeight * spatialScore)
                                );
                            """,
                            "params": {
                                "qMinX": q_minx,
                                "qMaxX": q_maxx,
                                "qMinY": q_miny,
                                "qMaxY": q_maxy,
                                "containmentWeight": containment_weight,
                                "overlapWeight": overlap_weight,
                                "spatialBoostWeight": max(0.0, BBOX_SPATIAL_BOOST_WEIGHT),
                            },
                        },
                    }
                }
            },
            overlap_context,
        )

    def _build_suggest(self) -> dict | None:
        query_text = self.search_criteria.get("query")
        if not query_text or not query_text.strip():
            return None

        return {
            "text": query_text,
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


@dataclass
class SearchExecutionResult:
    response_dict: dict
    source: str
    overlap_context: dict | None
    es_roundtrip_ms: float


class SearchExecutor:
    """Runs the Elasticsearch query and handles search-specific fallbacks."""

    def __init__(
        self,
        params: SearchParams,
        query_plan: SearchQueryPlan,
        facet_selection: SearchFacetSelection,
    ):
        self.params = params
        self.query_plan = query_plan
        self.facet_selection = facet_selection

    async def execute(self) -> SearchExecutionResult:
        try:
            response_dict, es_roundtrip_ms = await self._run_search(self._primary_kwargs())
            return SearchExecutionResult(
                response_dict=response_dict,
                source="primary",
                overlap_context=self.query_plan.overlap_context,
                es_roundtrip_ms=es_roundtrip_ms,
            )
        except NotFoundError:
            logger.warning(
                "Elasticsearch index '%s' not found; returning empty results",
                self.params.index_name,
            )
            return SearchExecutionResult(
                response_dict={
                    "hits": {"total": {"value": 0}, "hits": []},
                    "took": 0,
                    "aggregations": {},
                },
                source="missing_index",
                overlap_context=None,
                es_roundtrip_ms=0.0,
            )
        except Exception as es_error:
            logger.error(f"Elasticsearch error: {str(es_error)}", exc_info=True)
            fallback = await self._maybe_run_script_score_fallback(es_error)
            if fallback is not None:
                return fallback
            raise self._build_elasticsearch_http_error(es_error) from es_error

    def _primary_kwargs(self) -> dict:
        search_query = self.query_plan.search_query
        search_kwargs = {
            "index": self.params.index_name,
            "query": search_query["query"],
            "from_": self.params.skip,
            "size": self.params.limit,
            "sort": self.params.sort_clause,
            "track_total_hits": True,
            "suggest": search_query.get("suggest"),
        }
        if search_query.get("aggs"):
            search_kwargs["aggs"] = search_query["aggs"]
        return search_kwargs

    def _fallback_kwargs(self) -> dict:
        search_query = self.query_plan.search_query
        fallback_kwargs = {
            "index": self.params.index_name,
            "query": {"bool": self.query_plan.bool_query},
            "from_": self.params.skip,
            "size": self.params.limit,
            "sort": self.params.sort_clause,
            "track_total_hits": True,
            "suggest": search_query.get("suggest"),
        }
        if self.facet_selection.cached_aggregations is None and self.facet_selection.aggregations:
            fallback_kwargs["aggs"] = self.facet_selection.aggregations
        return fallback_kwargs

    async def _run_search(self, search_kwargs: dict) -> tuple[dict, float]:
        es_roundtrip_start = time.perf_counter()
        response = await es.search(**search_kwargs)
        es_roundtrip_ms = (time.perf_counter() - es_roundtrip_start) * 1000
        response_dict = response.body if hasattr(response, "body") else response
        return response_dict, es_roundtrip_ms

    async def _maybe_run_script_score_fallback(
        self,
        es_error: Exception,
    ) -> SearchExecutionResult | None:
        info = getattr(es_error, "info", {}) or {}
        error_type = info.get("error", {}).get("root_cause", [{}])[0].get("type", "")
        if "script_exception" not in error_type and "script_exception" not in str(es_error):
            return None

        logger.warning(
            "Script_score query failed (likely painless compile error); "
            "falling back to plain bool query without overlap scoring."
        )
        try:
            fallback_dict, es_roundtrip_ms = await self._run_search(self._fallback_kwargs())
            return SearchExecutionResult(
                response_dict=fallback_dict,
                source="script_score_fallback",
                overlap_context=None,
                es_roundtrip_ms=es_roundtrip_ms,
            )
        except Exception as fallback_error:
            logger.error(
                "Fallback bool query after script failure also errored: %s",
                fallback_error,
                exc_info=True,
            )
            return None

    def _build_elasticsearch_http_error(self, es_error: Exception) -> HTTPException:
        # Keep upstream query internals out of public 500 responses; the full
        # exception is already logged with exc_info in execute().
        error_detail = {
            "message": "Elasticsearch query failed",
            "code": "elasticsearch_query_failed",
        }
        if hasattr(es_error, "info"):
            info = getattr(es_error, "info", {}) or {}
            upstream_status = info.get("status") if isinstance(info, dict) else None
            if isinstance(upstream_status, int):
                error_detail["upstream_status_code"] = upstream_status
        if hasattr(es_error, "status_code"):
            status_code = es_error.status_code
            if isinstance(status_code, int):
                error_detail["upstream_status_code"] = status_code
        return HTTPException(status_code=500, detail=error_detail)


class SearchResponseBuilder:
    """Turns an ES response into the existing search_resources payload."""

    def __init__(
        self,
        params: SearchParams,
        search_criteria: dict,
        facet_service: FacetService,
        facet_selection: SearchFacetSelection,
        overall_start: float,
    ):
        self.params = params
        self.search_criteria = search_criteria
        self.facet_service = facet_service
        self.facet_selection = facet_selection
        self.overall_start = overall_start

    async def build(self, execution: SearchExecutionResult) -> dict:
        await self.facet_service.apply_to_response(
            execution.response_dict,
            self.facet_selection,
        )
        result = await process_search_response(
            execution.response_dict,
            self.params.limit,
            self.params.skip,
            self.search_criteria,
            overlap_context=execution.overlap_context,
            include_filters=self.params.include_filters,
            exclude_filters=self.params.exclude_filters,
            adv_q=self.params.adv_q,
            hydrate_hits=self.params.hydrate_hits,
        )
        self._log_timing(execution)
        return result

    def _log_timing(self, execution: SearchExecutionResult) -> None:
        total_ms = (time.perf_counter() - self.overall_start) * 1000
        response_hits = execution.response_dict.get("hits", {})
        total_hits_value = (response_hits.get("total") or {}).get("value")
        _log_aggregation_timing(
            operation="search_resources",
            cache_status=self.facet_selection.cache_status,
            total_ms=total_ms,
            es_roundtrip_ms=execution.es_roundtrip_ms,
            es_took_ms=float(execution.response_dict.get("took", 0) or 0),
            cache_lookup_ms=self.facet_selection.cache_lookup_ms,
            cache_store_ms=self.facet_selection.cache_store_ms,
            aggregation_names=self.facet_selection.names,
            total_hits=total_hits_value if total_hits_value is not None else None,
            hit_count=len(response_hits.get("hits", []) or []),
            source=execution.source,
        )


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
    hydrate_hits: bool = True,
):
    """Search resources in Elasticsearch with optional filters, sorting, and spelling
    suggestions."""
    params = SearchParams.from_inputs(
        query=query,
        fq=fq,
        skip=skip,
        limit=limit,
        sort=sort,
        search_fields=search_fields,
        include_filters=include_filters,
        exclude_filters=exclude_filters,
        facets=facets,
        adv_q=adv_q,
        hydrate_hits=hydrate_hits,
    )
    overall_start = time.perf_counter()

    try:
        search_criteria = params.criteria()
        logger.debug(f"Search criteria: {search_criteria}")

        facet_service = FacetService()
        facet_selection = await facet_service.prepare(params, search_criteria)
        query_plan = SearchQueryBuilder(
            params,
            search_criteria,
            facet_selection,
        ).build()

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("ES Query: %s", json.dumps(query_plan.search_query, indent=2))

        execution = await SearchExecutor(
            params,
            query_plan,
            facet_selection,
        ).execute()
        return await SearchResponseBuilder(
            params,
            search_criteria,
            facet_service,
            facet_selection,
            overall_start,
        ).build(execution)

    except Exception as e:
        logger.error(f"Search documents error: {str(e)}", exc_info=True)
        raise


def get_sort_options(search_criteria):
    """Generate sort options for the response."""
    base_url = os.getenv("APPLICATION_URL", "http://localhost:8000").rstrip("/") + "/api/v1/search"
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


def _global_count_from_aggs(aggs: dict) -> int:
    """Extract global-bucket doc_count for meta.mapStats.globalCount."""
    g = aggs.get("global_bucket_agg") or {}
    return int(g.get("doc_count", 0))


async def process_search_response(
    response,
    limit,
    skip,
    search_criteria,
    overlap_context: dict | None = None,
    include_filters: dict | None = None,
    exclude_filters: dict | None = None,
    adv_q: Optional[list] = None,
    hydrate_hits: bool = True,
):
    """Process Elasticsearch response and format for API output."""
    try:
        total_hits = response["hits"]["total"]["value"]
        logger.debug("Total hits: %s", total_hits)

        hits = response["hits"]["hits"]
        document_ids = [hit["_source"]["id"] for hit in hits]
        logger.debug("Found document IDs: %s", document_ids)

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
            aggs = response.get("aggregations", {})
            return {
                "status": "success",
                "queryTime": {
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
                    "suggestions": suggestions,
                    "mapStats": {"globalCount": _global_count_from_aggs(aggs)},
                },
                "data": [],
                "included": [],
            }

        processed_resources = []
        pg_query_time = 0.0

        # Precompute lookups from id -> score and bbox spatial metrics so we can
        # expose them in the API layer meta block.
        id_to_score: dict[str, float] = {}
        id_to_overlap: dict[str, float] = {}
        id_to_containment: dict[str, float] = {}
        id_to_spatial_score: dict[str, float] = {}

        def _compute_spatial_metrics(hit_dict: dict, ctx: dict) -> dict[str, float] | None:
            try:
                src = hit_dict.get("_source", {})
                d_minx = float(src["bbox_minx"])
                d_maxx = float(src["bbox_maxx"])
                d_miny = float(src["bbox_miny"])
                d_maxy = float(src["bbox_maxy"])
            except (KeyError, TypeError, ValueError):
                return None

            q_minx = float(ctx["qMinX"])
            q_maxx = float(ctx["qMaxX"])
            q_miny = float(ctx["qMinY"])
            q_maxy = float(ctx["qMaxY"])

            return _compute_bbox_spatial_metrics(
                d_minx=d_minx,
                d_maxx=d_maxx,
                d_miny=d_miny,
                d_maxy=d_maxy,
                q_minx=q_minx,
                q_maxx=q_maxx,
                q_miny=q_miny,
                q_maxy=q_maxy,
            )

        for hit in hits:
            rid = hit["_source"]["id"]
            id_to_score[rid] = hit.get("_score", 0.0)
            if overlap_context:
                metrics = _compute_spatial_metrics(hit, overlap_context)
                if metrics is not None:
                    id_to_overlap[rid] = metrics["overlap_ratio"]
                    id_to_containment[rid] = metrics["containment_ratio"]
                    id_to_spatial_score[rid] = metrics["spatial_score"]

        if hydrate_hits:
            start_time = time.time()
            # Create a CASE statement to preserve the order of document_ids
            order_case = (
                "CASE "
                + " ".join(
                    f"WHEN id = '{doc_id}' THEN {index}"
                    for index, doc_id in enumerate(document_ids)
                )
                + " END"
            )

            query = (
                resources.select()
                .where(resources.c.id.in_(document_ids))
                .order_by(text(order_case))
            )

            resource_rows = await database.fetch_all(query)
            distribution_contexts = await fetch_distribution_context_map(
                [resource["id"] for resource in resource_rows]
            )

            for resource in resource_rows:
                rid = resource["id"]
                distribution_context = distribution_contexts.get(rid)
                score = id_to_score.get(rid, 0.0)
                overlap_ratio = id_to_overlap.get(rid)
                containment_ratio = id_to_containment.get(rid)
                spatial_score = id_to_spatial_score.get(rid)

                doc: dict = {
                    "type": "document",
                    "id": rid,
                    "score": score,
                    "attributes": {
                        **resource,
                        **create_viewer_attributes(
                            resource, distribution_context=distribution_context
                        ),
                    },
                }
                if overlap_ratio is not None:
                    doc["bbox_overlap_ratio"] = overlap_ratio
                if containment_ratio is not None:
                    doc["bbox_containment_ratio"] = containment_ratio
                if spatial_score is not None:
                    doc["bbox_spatial_score"] = spatial_score

                processed_resources.append(doc)

            pg_query_time = (time.time() - start_time) * 1000
        else:
            for rid in document_ids:
                doc: dict = {
                    "type": "document",
                    "id": rid,
                    "score": id_to_score.get(rid, 0.0),
                }
                overlap_ratio = id_to_overlap.get(rid)
                containment_ratio = id_to_containment.get(rid)
                spatial_score = id_to_spatial_score.get(rid)
                if overlap_ratio is not None:
                    doc["bbox_overlap_ratio"] = overlap_ratio
                if containment_ratio is not None:
                    doc["bbox_containment_ratio"] = containment_ratio
                if spatial_score is not None:
                    doc["bbox_spatial_score"] = spatial_score
                processed_resources.append(doc)

        aggs = response.get("aggregations", {})
        included = [
            *process_aggregations(
                aggs,
                {
                    "q": search_criteria.get("query"),
                    "include_filters": include_filters,
                    "exclude_filters": exclude_filters,
                    "fq": search_criteria.get("filters"),
                    "adv_q": adv_q,
                },
            ),
            *get_sort_options(search_criteria),
        ]

        return {
            "status": "success",
            "queryTime": {
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
                "suggestions": suggestions,
                "mapStats": {"globalCount": _global_count_from_aggs(aggs)},
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
            detail={
                "message": "Failed to process search response",
                "code": "search_response_processing_failed",
            },
        ) from e


async def map_h3_aggregation(
    q: Optional[str] = None,
    fq: Optional[dict] = None,
    include_filters: Optional[dict] = None,
    exclude_filters: Optional[dict] = None,
    adv_q: Optional[list] = None,
    bbox: Optional[str] = None,
    resolution: int = 5,
) -> dict:
    """Run H3 terms agg + global count for map hex layer.

    bbox: 'west,south,east,north'. resolution: 2–8.
    Returns {"resolution": int, "hexes": [[h3_str, count], ...], "globalCount": int}.
    """
    index_name = os.getenv("ELASTICSEARCH_INDEX", "btaa_geospatial_api")
    if resolution < 2 or resolution > 8:
        resolution = 5
    filter_clauses = []
    must_not_clauses = []

    if fq:
        for field, values in fq.items():
            resolved = _resolve_filter_field(field)
            if isinstance(values, list):
                filter_clauses.append({"terms": {resolved: values}})
            else:
                filter_clauses.append({"term": {resolved: values}})

    if include_filters:
        # Apply location (bbox) filter so hex counts match the search results
        # (e.g. "Winnipeg" area).
        geo_filter = _build_geospatial_filter(include_filters.get("geo") or {})
        if geo_filter is not None:
            filter_clauses.append(geo_filter)
        for field, values in include_filters.items():
            if field == "geo":
                continue
            resolved = _resolve_filter_field(field)
            if field == "year_range" and isinstance(values, dict):
                yr = {"range": {"gbl_indexYear_im": {}}}
                if "start" in values:
                    try:
                        yr["range"]["gbl_indexYear_im"]["gte"] = int(values["start"])
                    except (ValueError, TypeError):
                        pass
                if "end" in values:
                    try:
                        yr["range"]["gbl_indexYear_im"]["lte"] = int(values["end"])
                    except (ValueError, TypeError):
                        pass
                if yr["range"]["gbl_indexYear_im"]:
                    filter_clauses.append(yr)
            elif isinstance(values, list):
                filter_clauses.append({"terms": {resolved: values}})
            else:
                filter_clauses.append({"term": {resolved: values}})

    if exclude_filters:
        for field, values in exclude_filters.items():
            resolved = _resolve_filter_field(field)
            if isinstance(values, list):
                must_not_clauses.append({"terms": {resolved: values}})
            else:
                must_not_clauses.append({"term": {resolved: values}})

    west, south, east, north = None, None, None, None
    if bbox:
        parts = [p.strip() for p in bbox.split(",")]
        if len(parts) == 4:
            try:
                west, south, east, north = (
                    float(parts[0]),
                    float(parts[1]),
                    float(parts[2]),
                    float(parts[3]),
                )
                # ES: lon in [-180,180], lat in [-90,90]; invalid values cause 400
                west = max(-180.0, min(180.0, west))
                east = max(-180.0, min(180.0, east))
                south = max(-90.0, min(90.0, south))
                north = max(-90.0, min(90.0, north))
                if west > east or south > north:
                    west, south, east, north = None, None, None, None
            except (ValueError, TypeError):
                west, south, east, north = None, None, None, None
    if west is not None and south is not None and east is not None and north is not None:
        filter_clauses.append(
            {
                "geo_bounding_box": {
                    "dcat_centroid": {
                        "top_left": {"lat": north, "lon": west},
                        "bottom_right": {"lat": south, "lon": east},
                    }
                }
            }
        )

    must_clauses = []
    should_clauses = []
    combined_must_not = list(must_not_clauses)

    if q and str(q).strip():
        escaped_q = _escape_query_string_brackets(str(q).strip())
        must_clauses.append(
            {
                "query_string": {
                    "query": escaped_q,
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

    if adv_q:
        advanced_query_structure = _build_advanced_query(adv_q)
        must_clauses.extend(advanced_query_structure["must"])
        should_clauses.extend(advanced_query_structure["should"])
        combined_must_not.extend(advanced_query_structure["must_not"])

    def build_bool_query(active_filters: list[dict]) -> dict:
        bool_query: dict = {}

        if must_clauses:
            bool_query["must"] = must_clauses
        elif not should_clauses:
            bool_query["must"] = [{"match_all": {}}]

        if should_clauses:
            bool_query["should"] = should_clauses
            bool_query["minimum_should_match"] = 1

        if active_filters:
            bool_query["filter"] = active_filters

        if combined_must_not:
            bool_query["must_not"] = combined_must_not

        return bool_query

    bool_query = build_bool_query(filter_clauses)

    # Larger bucket size for global requests (no bbox) so more hexes are returned.
    h3_terms_size = 10000 if bbox is None else 5000
    aggs = {
        "h3_terms": {
            "terms": {"field": f"h3_res{resolution}", "size": h3_terms_size, "min_doc_count": 1}
        },
        "global_bucket_agg": _global_bucket_aggregation(),
    }

    try:
        resp = await es.search(
            index=index_name,
            query={"bool": bool_query},
            size=0,
            track_total_hits=False,
            aggs=aggs,
        )
    except NotFoundError:
        return {"resolution": resolution, "hexes": [], "globalCount": 0}
    except Exception as e:
        logger.exception(
            "map_h3_aggregation failed (index=%s, resolution=%s): %s",
            index_name,
            resolution,
            e,
        )
        return {"resolution": resolution, "hexes": [], "globalCount": 0}

    try:
        body = resp.body if hasattr(resp, "body") else resp
        agg_data = body.get("aggregations", {})
        buckets = (agg_data.get("h3_terms") or {}).get("buckets", [])
        # Compact facet-style [h3, count] tuples (smaller payload than {"h3","count"} per item)
        hexes = [[b["key"], b["doc_count"]] for b in buckets]

        # Global count: when viewport bbox is applied, run a second query without bbox
        # so global count is search-scoped, not map-scoped.
        has_bbox = any("geo_bounding_box" in c for c in filter_clauses)
        if has_bbox:
            rest = [c for c in filter_clauses if "geo_bounding_box" not in c]
            bool_no_bbox = build_bool_query(rest)
            try:
                g_resp = await es.search(
                    index=index_name,
                    query={"bool": bool_no_bbox},
                    size=0,
                    track_total_hits=False,
                    aggs={"global_bucket_agg": aggs["global_bucket_agg"]},
                )
                g_body = g_resp.body if hasattr(g_resp, "body") else g_resp
                global_count = int(
                    (g_body.get("aggregations", {}).get("global_bucket_agg") or {}).get(
                        "doc_count", 0
                    )
                )
            except (NotFoundError, Exception):
                global_count = 0
        else:
            global_count = int((agg_data.get("global_bucket_agg") or {}).get("doc_count", 0))

        return {"resolution": resolution, "hexes": hexes, "globalCount": global_count}
    except Exception as e:
        logger.exception(
            "map_h3_aggregation response handling failed (resolution=%s): %s",
            resolution,
            e,
        )
        return {"resolution": resolution, "hexes": [], "globalCount": 0}


def _flatten_bracket_params(prefix: str, value) -> list[tuple[str, str]]:
    """
    Flatten nested objects into bracket-style query params.

    Example:
      prefix='include_filters[geo]' and value={'top_left': {'lat': 1}}
      -> [('include_filters[geo][top_left][lat]', '1')]
    """

    params: list[tuple[str, str]] = []

    def _walk(key_prefix: str, v):
        if v is None:
            return
        if isinstance(v, dict):
            for k, child in v.items():
                _walk(f"{key_prefix}[{k}]", child)
            return
        if isinstance(v, (list, tuple)):
            for i, child in enumerate(v):
                _walk(f"{key_prefix}[{i}]", child)
            return
        params.append((key_prefix, str(v)))

    _walk(prefix, value)
    return params


def generate_facet_apply_template(facet_id: str, search_context: dict) -> str:
    """
    Generate a single URL template to apply a facet value while preserving the
    current search context.

    Placeholder: `{value}` (caller should URL-encode substituted value).
    """

    base_url = os.getenv("APPLICATION_URL", "http://localhost:8000") + "/api/v1/search"

    q = (search_context or {}).get("q") or ""
    include_filters = (search_context or {}).get("include_filters") or {}
    exclude_filters = (search_context or {}).get("exclude_filters") or {}
    fq = (search_context or {}).get("fq") or {}
    adv_q = (search_context or {}).get("adv_q")

    query_params: dict[str, list[str] | str] = {"q": q}

    # Preserve advanced query clauses if present (as a compact JSON string)
    if adv_q:
        try:
            query_params["adv_q"] = json.dumps(adv_q, separators=(",", ":"))
        except Exception:
            # If something unexpected is passed, just skip it rather than breaking links
            pass

    # Preserve include filters (new style). Geo is nested.
    if isinstance(include_filters, dict):
        for field, values in include_filters.items():
            if field == "geo" and isinstance(values, dict):
                for k, v in _flatten_bracket_params("include_filters[geo]", values):
                    query_params.setdefault(k, []).append(v)  # type: ignore[arg-type]
                continue

            if isinstance(values, list):
                for v in values:
                    query_params.setdefault(f"include_filters[{field}][]", []).append(str(v))  # type: ignore[arg-type]
            else:
                query_params.setdefault(f"include_filters[{field}][]", []).append(str(values))  # type: ignore[arg-type]

    # Preserve exclude filters (new style).
    if isinstance(exclude_filters, dict):
        for field, values in exclude_filters.items():
            if isinstance(values, list):
                for v in values:
                    query_params.setdefault(f"exclude_filters[{field}][]", []).append(str(v))  # type: ignore[arg-type]
            else:
                query_params.setdefault(f"exclude_filters[{field}][]", []).append(str(values))  # type: ignore[arg-type]

    # Preserve legacy fq filters by converting them to include_filters in the URL.
    # Note: fq keys may include `.keyword` suffix from ES field resolution.
    if isinstance(fq, dict):
        for field, values in fq.items():
            facet_key = str(field).replace(".keyword", "")
            if isinstance(values, list):
                for v in values:
                    query_params.setdefault(f"include_filters[{facet_key}][]", []).append(str(v))  # type: ignore[arg-type]
            else:
                query_params.setdefault(f"include_filters[{facet_key}][]", []).append(str(values))  # type: ignore[arg-type]

    # Add the facet value placeholder to apply this facet.
    sentinel = "__FACET_VALUE__"
    query_params.setdefault(f"include_filters[{facet_id}][]", []).append(sentinel)  # type: ignore[arg-type]

    # urlencode will percent-encode the sentinel safely; swap it back to `{value}`.
    query_string = urlencode(query_params, doseq=True)
    query_string = query_string.replace(sentinel, "{value}")
    return f"{base_url}?{query_string}"


def process_aggregations(aggregations, search_context: dict):
    """Transform Elasticsearch aggregations into JSON:API includes."""
    # Define custom labels for aggregations
    agg_labels = {
        "id_agg": "ID",
        "spatial_agg": "Spatial Coverage",
        "resource_class_agg": "Resource Class",
        "resource_type_agg": "Resource Type",
        "index_year_agg": "Index Year",
        "time_period": "Time Period",
        "b1g_language_sm": "Language",
        "dct_language_sm": "Language",
        "language_agg": "Language",
        "creator_agg": "Creator",
        "dct_publisher_sm": "Publisher",
        "provider_agg": "Provider",
        "b1g_code_s": "B1G Code",
        "ogm_repo": "OGM Repo",
        "access_rights_agg": "Access Rights",
        "georeferenced_agg": "Georeferenced",
        "gbl_georeferenced_b": "Georeferenced",
        "b1g_georeferenced_allmaps_b": "Map Overlay",
        "geo_country_agg": "Country",
        "geo_region_agg": "Region",
        "geo_county_agg": "County",
    }

    processed_facets = []

    # Define time_period ordering (most recent first)
    time_period_order = [
        "2025-present",
        "2020-2024",
        "2015-2019",
        "2010-2014",
        "2005-2009",
        "2000-2004",
        "1950-1999",
        "1900-1949",
        "1850-1899",
        "1800-1849",
        "1700s",
        "1600s",
        "1500s",
        "1400s-earlier",
    ]

    # Process regular aggregations
    for agg_name, agg_data in aggregations.items():
        if agg_name == "global_bucket_agg":
            continue
        buckets = agg_data.get("buckets", [])

        # Special handling for time_period to enforce chronological order
        if agg_name == "time_period":
            # Create a lookup for buckets by key
            bucket_dict = {bucket["key"]: bucket for bucket in buckets}
            # Order buckets according to time_period_order
            ordered_buckets = []
            for period in time_period_order:
                if period in bucket_dict:
                    ordered_buckets.append(bucket_dict[period])
        # Special handling for histogram aggregation
        elif agg_name == "year_histogram":
            # Pass histogram buckets directly, but ensure they are sorted by key (year)
            # Elastic histogram buckets are typically sorted by key ascending
            ordered_buckets = buckets
        else:
            ordered_buckets = buckets

        # Determine type based on aggregation name
        facet_type = "timeline" if agg_name == "year_histogram" else "facet"

        processed_facets.append(
            {
                "type": facet_type,
                "id": agg_name,
                "links": {"applyTemplate": generate_facet_apply_template(agg_name, search_context)},
                "attributes": {
                    "label": agg_labels.get(
                        agg_name, agg_name.replace("_sm", "").replace("_", " ").title()
                    ),
                    # Compact encoding: [value, hits]
                    "items": [[bucket["key"], bucket["doc_count"]] for bucket in ordered_buckets],
                },
            }
        )

    return processed_facets


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
        facet_name: The facet field name (e.g., 'dct_spatial_sm',
            'schema_provider_s', 'time_period')
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
    overall_start = time.perf_counter()

    # Get facet aggregation configuration
    facet_config = get_facet_aggregation_config(facet_name)
    agg_field = facet_config["field"]

    # Build the same filter query structure as search_resources
    filter_clauses = []
    must_not_clauses = []

    if fq:
        for field, values in fq.items():
            resolved_field = _resolve_filter_field(field)
            if isinstance(values, list):
                filter_clauses.append({"terms": {resolved_field: values}})
            else:
                filter_clauses.append({"term": {resolved_field: values}})

    if include_filters:
        for field, values in include_filters.items():
            resolved_field = _resolve_filter_field(field)

            # Handle geospatial queries
            if field == "geo" and isinstance(values, dict):
                geo_filter = _build_geospatial_filter(values)
                if geo_filter:
                    filter_clauses.append(geo_filter)
            # Handle year range queries (same logic as search_resources)
            elif field == "year_range" and isinstance(values, dict):
                year_range_filter = {"range": {"gbl_indexYear_im": {}}}
                if "start" in values:
                    try:
                        year_range_filter["range"]["gbl_indexYear_im"]["gte"] = int(values["start"])
                    except (ValueError, TypeError):
                        pass
                if "end" in values:
                    try:
                        year_range_filter["range"]["gbl_indexYear_im"]["lte"] = int(values["end"])
                    except (ValueError, TypeError):
                        pass
                if year_range_filter["range"]["gbl_indexYear_im"]:
                    filter_clauses.append(year_range_filter)
            elif field in ("geo_global", "geo_or_near_global") and isinstance(values, list):
                if values and str(values[0]).lower() == "true":
                    filter_clauses.append({"term": {resolved_field: True}})
            elif isinstance(values, list):
                # Use terms to match if ANY of the specified values are present
                # This matches the behavior of legacy fq filters (OR logic)
                filter_clauses.append({"terms": {resolved_field: values}})
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
                    "query": _escape_query_string_brackets(query_text),
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

    # Narrow the bucket list in Elasticsearch so autocomplete doesn't pull unrelated values.
    # Keyword-field regex matching is case-sensitive, so build an explicit case-insensitive
    # pattern rather than relying solely on the later client-side filtering step.
    if q_facet:
        agg_config["terms"]["include"] = _build_case_insensitive_facet_regex(q_facet)

    search_query = {
        "query": {"bool": bool_query_dict},
        "size": 0,  # We only want aggregations, not documents
        "aggs": {"facet_values": agg_config},
    }

    cache_key = _build_facet_values_cache_key(
        index_name=index_name,
        facet_name=facet_name,
        query=query,
        fq=fq,
        include_filters=include_filters,
        exclude_filters=exclude_filters,
        adv_q=adv_q,
        q_facet=q_facet,
        size=size,
    )
    cache_lookup_start = time.perf_counter()
    cached_buckets = await _get_cached_facet_values(cache_key)
    cache_lookup_ms = (time.perf_counter() - cache_lookup_start) * 1000
    if cached_buckets is not None:
        _log_aggregation_timing(
            operation="get_facet_values",
            cache_status="hit",
            total_ms=(time.perf_counter() - overall_start) * 1000,
            es_roundtrip_ms=0.0,
            es_took_ms=0.0,
            cache_lookup_ms=cache_lookup_ms,
            cache_store_ms=0.0,
            aggregation_names=(facet_name,),
            total_hits=len(cached_buckets),
            source="cache",
        )
        return cached_buckets

    try:
        es_roundtrip_start = time.perf_counter()
        response = await es.search(
            index=index_name,
            query=search_query["query"],
            size=0,
            aggs=search_query["aggs"],
        )
        es_roundtrip_ms = (time.perf_counter() - es_roundtrip_start) * 1000
        response_dict = response.body if hasattr(response, "body") else response
        buckets = response_dict.get("aggregations", {}).get("facet_values", {}).get("buckets", [])
        cache_store_start = time.perf_counter()
        await _store_cached_facet_values(cache_key, facet_name, buckets)
        cache_store_ms = (time.perf_counter() - cache_store_start) * 1000
        _log_aggregation_timing(
            operation="get_facet_values",
            cache_status="miss",
            total_ms=(time.perf_counter() - overall_start) * 1000,
            es_roundtrip_ms=es_roundtrip_ms,
            es_took_ms=float(response_dict.get("took", 0) or 0),
            cache_lookup_ms=cache_lookup_ms,
            cache_store_ms=cache_store_ms,
            aggregation_names=(facet_name,),
            total_hits=len(buckets),
            source="primary",
        )
        return buckets
    except Exception as es_error:
        logger.error(f"Elasticsearch error getting facet values: {str(es_error)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Elasticsearch facet lookup failed",
                "code": "elasticsearch_facet_lookup_failed",
            },
        ) from es_error


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

    # Define time_period chronological order (most recent first)
    time_period_order = [
        "2025-present",
        "2020-2024",
        "2015-2019",
        "2010-2014",
        "2005-2009",
        "2000-2004",
        "1950-1999",
        "1900-1949",
        "1850-1899",
        "1800-1849",
        "1700s",
        "1600s",
        "1500s",
        "1400s-earlier",
    ]

    # Special handling for time_period - default to chronological order
    if facet_name == "time_period" and sort == "count_desc":
        # Use chronological order for time_period by default
        bucket_dict = {bucket["key"]: bucket for bucket in filtered_buckets}
        filtered_buckets = []
        for period in time_period_order:
            if period in bucket_dict:
                filtered_buckets.append(bucket_dict[period])
    # Sort buckets based on sort parameter
    elif sort == "count_desc":
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
        # Default to count_desc (or chronological for time_period)
        if facet_name == "time_period":
            bucket_dict = {bucket["key"]: bucket for bucket in filtered_buckets}
            filtered_buckets = []
            for period in time_period_order:
                if period in bucket_dict:
                    filtered_buckets.append(bucket_dict[period])
        else:
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

        facet_items.append(
            {
                "type": "facet_value",
                "id": str(facet_value),
                "attributes": {
                    # Minimal payload: label is redundant (frontend can render String(value))
                    "value": facet_value,
                    "hits": doc_count,
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


async def find_similar_resources(resource_id: str, limit: int = 12) -> list:
    """
    Find similar resources using Elasticsearch more_like_this query.

    Args:
        resource_id: The ID of the resource to find similar items for
        limit: Maximum number of similar resources to return (default: 12)

    Returns:
        List of resource IDs ordered by similarity score
    """
    index_name = os.getenv("ELASTICSEARCH_INDEX", "btaa_geospatial_api")

    try:
        # First, check if the resource exists in Elasticsearch
        try:
            doc = await es.get(index=index_name, id=resource_id)
            if not doc:
                logger.warning(f"Resource {resource_id} not found in Elasticsearch")
                return []
        except NotFoundError:
            logger.warning(f"Resource {resource_id} not found in Elasticsearch")
            return []

        # Build more_like_this query
        # Fields to use for similarity matching
        similar_fields = [
            "dct_title_s",
            "dct_description_sm",
            "summary",
            "dct_creator_sm",
            "dct_subject_sm",
            "dcat_keyword_sm",
        ]

        mlt_query = {
            "bool": {
                "must": [
                    {
                        "more_like_this": {
                            "fields": similar_fields,
                            "like": [{"_id": resource_id}],
                            "min_term_freq": 1,
                            "min_doc_freq": 1,
                            "max_query_terms": 25,
                            "minimum_should_match": "30%",
                        }
                    }
                ],
                "must_not": [{"term": {"id": resource_id}}],
            }
        }

        # Execute the query
        response = await es.search(
            index=index_name,
            query=mlt_query,
            size=limit,
        )
        response_dict = response.body if hasattr(response, "body") else response

        # Extract resource IDs from results
        hits = response_dict.get("hits", {}).get("hits", [])
        similar_ids = [hit["_source"].get("id") for hit in hits if hit.get("_source", {}).get("id")]

        logger.debug("Found %s similar resources for %s", len(similar_ids), resource_id)
        return similar_ids

    except Exception as e:
        logger.error(f"Error finding similar resources for {resource_id}: {str(e)}", exc_info=True)
        return []
