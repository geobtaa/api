import json
import logging
import math
import os
import re
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from shapely import wkt as shapely_wkt
from shapely.geometry import mapping as shapely_mapping

from db.database import database
from db.models import resources

from .client import es

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)


def _get_failure_logger():
    """Return a dedicated logger that writes indexing failures to a file.

    The file path can be customized via the INDEX_FAILURE_LOG env var. Defaults to
    logs/index_failures.log relative to the project/app working directory.
    """
    failure_log_path = os.getenv("INDEX_FAILURE_LOG", "logs/index_failures.log")
    # Ensure directory exists
    try:
        Path(failure_log_path).parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        # If we cannot create the directory, fall back to stdout logging only
        return logger

    failure_logger = logging.getLogger("elasticsearch_index_failures")
    if not any(
        isinstance(h, logging.FileHandler)
        and getattr(h, "baseFilename", None)
        and str(h.baseFilename) == str(Path(failure_log_path))
        for h in failure_logger.handlers
    ):
        file_handler = logging.FileHandler(failure_log_path)
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        failure_logger.addHandler(file_handler)
        failure_logger.propagate = False
        failure_logger.setLevel(logging.INFO)
    return failure_logger


def _coerce_date(value):
    """Return an ISO8601 date string acceptable to Elasticsearch or None.

    Accepts common variants: YYYY, YYYY-MM, YYYY-MM-DD, full ISO datetimes.
    Falls back to None if parsing fails.
    """
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        # Interpret as year if reasonable
        try:
            if 1000 <= int(value) <= 3000:
                return f"{int(value):04d}-01-01"
        except Exception:
            return None
        return None
    if not isinstance(value, str):
        return None
    text = value.strip()
    # Pure year
    if text.isdigit() and 4 <= len(text) <= 4:
        return f"{int(text):04d}-01-01"
    # YYYY-MM
    try:
        if len(text) == 7 and text[4] == "-":
            dt = datetime.strptime(text, "%Y-%m")
            return dt.strftime("%Y-%m-01")
    except Exception:
        pass
    # YYYY-MM-DD (or full ISO)
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            dt = datetime.strptime(text, fmt)
            return dt.strftime("%Y-%m-%d")
        except Exception:
            continue
    # Last resort: fromisoformat without tz
    try:
        dt = datetime.fromisoformat(text.replace("Z", ""))
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return None


def _coerce_integer_or_list(value):
    """Coerce a value or list of values to integers; drop invalids; return None if empty."""

    def to_int(v):
        try:
            if isinstance(v, bool):
                return None
            return int(str(v).strip())
        except Exception:
            return None

    if isinstance(value, list):
        ints = [iv for iv in (to_int(v) for v in value) if iv is not None]
        return ints if ints else None
    iv = to_int(value)
    return iv if iv is not None else None


def _calculate_time_period_from_year(year_value):
    """Calculate the time period bucket for a given year value.

    Args:
        year_value: Integer year value or list of integers (takes first year if list)

    Returns:
        String representing the time period bucket, or None if no valid year
    """
    # Handle list/array of years - use the first one
    if isinstance(year_value, list):
        if not year_value:
            return None
        year_value = year_value[0]

    # Handle None or invalid values
    if year_value is None:
        return None

    # Convert to int if possible
    try:
        year = int(year_value)
    except (ValueError, TypeError):
        return None

    # Calculate time period
    if year < 1400:
        return "1400s-earlier"
    elif year < 1500:
        return "1400s-earlier"
    elif year < 1600:
        return "1500s"
    elif year < 1700:
        return "1600s"
    elif year < 1800:
        return "1700s"
    elif year < 1850:
        return "1800-1849"
    elif year < 1900:
        return "1850-1899"
    elif year < 1950:
        return "1900-1949"
    elif year < 2000:
        return "1950-1999"
    elif year < 2005:
        return "2000-2004"
    elif year < 2010:
        return "2005-2009"
    elif year < 2015:
        return "2010-2014"
    elif year < 2020:
        return "2015-2019"
    elif year < 2025:
        return "2020-2024"
    else:
        return "2025-present"


def _coerce_boolean(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        t = value.strip().lower()
        if t in ("true", "t", "1", "yes", "y"):
            return True
        if t in ("false", "f", "0", "no", "n"):
            return False
    if isinstance(value, (int, float)):
        return bool(value)
    return None


async def index_resources():
    """Index all resources from PostgreSQL into Elasticsearch."""
    index_name = os.getenv("ELASTICSEARCH_INDEX", "btaa_geospatial_api")

    if await es.indices.exists(index=index_name):
        await es.indices.delete(index=index_name)

    from .client import init_elasticsearch

    await init_elasticsearch()

    resource_rows = await database.fetch_all(resources.select())
    processed_resources = await prepare_bulk_data(resource_rows, index_name)

    if processed_resources:
        return await perform_individual_indexing(processed_resources, index_name)

    return {"message": "No resources to index"}


async def prepare_bulk_data(resources, index_name):
    """Prepare resources for indexing (now using individual operations for reliability)."""
    processed_resources = []
    for resource in resources:
        resource_dict = await process_resource(dict(resource))
        if resource_dict:  # Only add if processing succeeded
            processed_resources.append(resource_dict)
    return processed_resources


async def process_resource(resource_dict):
    """Process a single resource for indexing."""
    processed_dict = {}

    date_fields = {"gbl_mdmodified_dt", "b1g_dateAccessioned_s", "b1g_dateRetired_s"}
    integer_fields = {"gbl_indexYear_im"}
    boolean_fields = {"gbl_georeferenced_b", "b1g_child_record_b"}

    for key, value in resource_dict.items():
        if isinstance(value, (list, tuple)):
            processed_dict[key] = list(value)
        elif key in date_fields:
            processed_dict[key] = _coerce_date(value)
        elif key in integer_fields:
            processed_dict[key] = _coerce_integer_or_list(value)
        elif key in boolean_fields:
            processed_dict[key] = _coerce_boolean(value)
        elif key == "dct_references_s":
            # Legacy field deprecated in favor of resource_distributions
            continue
        # Handle geometry fields
        elif key in ["locn_geometry", "dcat_bbox", "dcat_centroid"]:
            # Store original string value
            processed_dict[f"{key}_original"] = value
            if not value:
                processed_dict[key] = None
            else:
                processed_geometry = process_geometry(value)
                if key == "dcat_centroid":
                    # Mapping is geo_point: must be [lon, lat] or {"lon":..,"lat":..}
                    if (
                        processed_geometry
                        and isinstance(processed_geometry, dict)
                        and processed_geometry.get("type", "").lower() == "point"
                    ):
                        coords = processed_geometry.get("coordinates")
                        processed_dict[key] = (
                            coords
                            if isinstance(coords, (list, tuple)) and len(coords) >= 2
                            else None
                        )
                    else:
                        processed_dict[key] = None
                else:
                    # geo_shape fields expect a GeoJSON-like dict
                    if processed_geometry:
                        if "type" in processed_geometry:
                            normalized_type = _normalize_geojson_type(
                                processed_geometry.get("type")
                            )
                            if normalized_type:
                                processed_geometry["type"] = normalized_type
                        processed_dict[key] = processed_geometry
                        # When we have a normalized bbox geometry, compute numeric bbox metrics
                        if key == "dcat_bbox":
                            _update_bbox_metrics(processed_dict, processed_geometry)
                    else:
                        processed_dict[key] = None
        else:
            processed_dict[key] = value

    # Add top-level summary only to avoid dynamic mapping conflicts
    summaries = await get_resource_summaries(processed_dict["id"])
    if summaries:
        first = summaries[0]
        processed_dict["summary"] = first.get("summary") or None

    # Calculate and add time_period facet
    time_period = _calculate_time_period_from_year(processed_dict.get("gbl_indexYear_im"))
    if time_period:
        processed_dict["time_period"] = time_period

    # Calculate and add time_period facet from gbl_indexYear_im
    time_period = _calculate_time_period_from_year(processed_dict.get("gbl_indexYear_im"))
    if time_period:
        processed_dict["time_period"] = time_period

    # Add spatial facet data
    spatial_facets = await get_spatial_facets(processed_dict["id"])
    if spatial_facets:
        processed_dict["geo_global"] = spatial_facets.get("geo_global", False)
        processed_dict["geo_country"] = spatial_facets.get("geo_country")
        processed_dict["geo_region"] = spatial_facets.get("geo_region")
        processed_dict["geo_county"] = spatial_facets.get("geo_county")

    # Clean and prepare suggestion inputs
    suggestion_inputs = []

    # Add title if it exists
    if title := processed_dict.get("dct_title_s"):
        suggestion_inputs.append(title)

    # Add creators
    if creators := processed_dict.get("dct_creator_sm"):
        if isinstance(creators, list):
            suggestion_inputs.extend(creators)
        else:
            suggestion_inputs.append(creators)

    # Add publishers
    if publishers := processed_dict.get("dct_publisher_sm"):
        if isinstance(publishers, list):
            suggestion_inputs.extend(publishers)
        else:
            suggestion_inputs.append(publishers)

    # Add provider
    if provider := processed_dict.get("schema_provider_s"):
        suggestion_inputs.append(provider)

    # Add subjects
    if subjects := processed_dict.get("dct_subject_sm"):
        if isinstance(subjects, list):
            suggestion_inputs.extend(subjects)
        else:
            suggestion_inputs.append(subjects)

    # Add spatial
    if spatial := processed_dict.get("dct_spatial_sm"):
        if isinstance(spatial, list):
            suggestion_inputs.extend(spatial)
        else:
            suggestion_inputs.append(spatial)

    # Add keywords
    if keywords := processed_dict.get("dcat_keyword_sm"):
        if isinstance(keywords, list):
            suggestion_inputs.extend(keywords)
        else:
            suggestion_inputs.append(keywords)

    # Filter out None values and empty strings
    suggestion_inputs = [s for s in suggestion_inputs if s and str(s).strip()]
    # Coerce to strings and truncate to match completion max_input_length (50)
    suggestion_inputs = [str(s).strip()[:50] for s in suggestion_inputs]
    # Remove empties after truncation and de-duplicate while preserving order
    seen = set()
    deduped = []
    for s in suggestion_inputs:
        if s and s not in seen:
            seen.add(s)
            deduped.append(s)
    suggestion_inputs = deduped

    # Get resource classes, ensuring it's a list and has at least one value
    resource_classes = processed_dict.get("gbl_resourceClass_sm", [])
    if isinstance(resource_classes, str):
        resource_classes = [resource_classes]
    if not resource_classes:
        resource_classes = ["none"]

    # Add suggestion field with cleaned data - removed contexts
    processed_dict["suggest"] = {"input": suggestion_inputs}

    return processed_dict


async def get_resource_summaries(resource_id):
    """Get summaries for an resource."""
    try:
        query = """
            SELECT enrichment_id, ai_provider, model, response, created_at
            FROM resource_ai_enrichments
            WHERE resource_id = :resource_id
            ORDER BY created_at DESC
        """
        summaries = await database.fetch_all(query, {"resource_id": resource_id})

        # Process summaries
        processed_summaries = []
        for summary in summaries:
            summary_dict = dict(summary)

            # Extract the summary text from the response JSON
            if summary_dict.get("response"):
                try:
                    response_data = (
                        json.loads(summary_dict["response"])
                        if isinstance(summary_dict["response"], str)
                        else summary_dict["response"]
                    )
                    summary_dict["summary"] = response_data.get("summary", "")
                except (json.JSONDecodeError, AttributeError):
                    summary_dict["summary"] = ""

            processed_summaries.append(summary_dict)

        return processed_summaries
    except Exception as e:
        print(f"Error getting summaries for resource {resource_id}: {str(e)}")
        return []


async def get_spatial_facets(resource_id):
    """Get spatial facets for a resource."""
    try:
        query = """
            SELECT geo_global, geo_country, geo_region, geo_county
            FROM resource_spatial_facets
            WHERE resource_id = :resource_id
        """
        result = await database.fetch_one(query, {"resource_id": resource_id})

        if result:
            spatial_facets = dict(result)

            # Parse JSON fields and format as pipe-delimited strings for faceting
            if spatial_facets.get("geo_country"):
                try:
                    country_data = json.loads(spatial_facets["geo_country"])
                    if isinstance(country_data, dict) and all(
                        key in country_data for key in ["wok_id", "parent_id", "name"]
                    ):
                        # Format: wok_id|parent_id|name
                        spatial_facets["geo_country"] = (
                            f"{country_data['wok_id']}|{country_data['parent_id']}|{country_data['name']}"
                        )
                    else:
                        spatial_facets["geo_country"] = None
                except (json.JSONDecodeError, TypeError):
                    spatial_facets["geo_country"] = None

            if spatial_facets.get("geo_region"):
                try:
                    region_data = json.loads(spatial_facets["geo_region"])
                    if isinstance(region_data, list):
                        # Format each region as: wok_id|parent_id|name
                        region_strings = []
                        for region in region_data:
                            if isinstance(region, dict) and all(
                                key in region for key in ["wok_id", "parent_id", "name"]
                            ):
                                region_strings.append(
                                    f"{region['wok_id']}|{region['parent_id']}|{region['name']}"
                                )
                        spatial_facets["geo_region"] = region_strings if region_strings else None
                    else:
                        spatial_facets["geo_region"] = None
                except (json.JSONDecodeError, TypeError):
                    spatial_facets["geo_region"] = None

            if spatial_facets.get("geo_county"):
                try:
                    county_data = json.loads(spatial_facets["geo_county"])
                    if isinstance(county_data, list):
                        # Format each county as: wok_id|parent_id|state_abbrev|name
                        county_strings = []
                        for county in county_data:
                            if isinstance(county, dict) and all(
                                key in county
                                for key in ["wok_id", "parent_id", "state_abbrev", "name"]
                            ):
                                county_strings.append(
                                    f"{county['wok_id']}|{county['parent_id']}|{county['state_abbrev']}|{county['name']}"
                                )
                        spatial_facets["geo_county"] = county_strings if county_strings else None
                    else:
                        spatial_facets["geo_county"] = None
                except (json.JSONDecodeError, TypeError):
                    spatial_facets["geo_county"] = None

            return spatial_facets
        return None
    except Exception as e:
        logger.error(f"Error getting spatial facets for resource {resource_id}: {str(e)}")
        return None


def _convert_tuples_to_lists(value):
    """Recursively convert tuples to lists and coerce numeric strings to floats."""
    if isinstance(value, dict):
        return {key: _convert_tuples_to_lists(val) for key, val in value.items()}
    if isinstance(value, tuple):
        return [_convert_tuples_to_lists(v) for v in value]
    if isinstance(value, list):
        return [_convert_tuples_to_lists(v) for v in value]
    if isinstance(value, str):
        stripped = value.strip()
        try:
            return float(stripped)
        except (TypeError, ValueError):
            return value
    return value


def _normalize_geojson_type(type_name):
    """Normalize GeoJSON type casing."""
    if not isinstance(type_name, str):
        return None
    mapping_table = {
        "point": "Point",
        "polygon": "Polygon",
        "multipolygon": "MultiPolygon",
        "linestring": "LineString",
        "multilinestring": "MultiLineString",
        "envelope": "Envelope",
    }
    lower = type_name.lower()
    return mapping_table.get(lower, type_name)


def _normalize_geojson_geometry(geometry_dict):
    """Validate and normalize a GeoJSON-like geometry dictionary."""
    if not isinstance(geometry_dict, dict):
        return None

    normalized = _convert_tuples_to_lists(geometry_dict)
    geom_type = _normalize_geojson_type(normalized.get("type"))
    coords = normalized.get("coordinates")

    if not geom_type or coords is None:
        return None

    geom_type_lower = geom_type.lower()

    if geom_type_lower == "point":
        if isinstance(coords, list) and len(coords) >= 2:
            coords = [coords[0], coords[1]]
        elif isinstance(coords, (tuple, set)) and len(coords) >= 2:
            coords = [coords[0], coords[1]]
        else:
            return None

        try:
            coords = [float(coords[0]), float(coords[1])]
        except (TypeError, ValueError):
            return None

        if not _is_valid_point(coords):
            logger.warning(f"Invalid point coordinates: {coords} - skipping")
            return None

        return {"type": "Point", "coordinates": coords}

    if geom_type_lower == "polygon":
        if not _is_valid_polygon_coordinates(coords, "polygon"):
            logger.warning(f"Invalid polygon coordinates: {coords} - skipping")
            return None
        return {"type": "Polygon", "coordinates": coords}

    if geom_type_lower == "multipolygon":
        if not _is_valid_polygon_coordinates(coords, "multipolygon"):
            logger.warning(f"Invalid multipolygon coordinates: {coords} - skipping")
            return None
        return {"type": "MultiPolygon", "coordinates": coords}

    return None


def _convert_bbox_string_to_envelope(geometry):
    """Handle bbox strings formatted as 'minx,miny,maxx,maxy'."""
    parts = [p.strip() for p in geometry.split(",")]
    if len(parts) != 4:
        return None
    try:
        minx, miny, maxx, maxy = map(float, parts)
    except ValueError:
        return None

    normalized_geom, error_msg = _normalize_envelope(minx, maxx, maxy, miny)
    if normalized_geom is None:
        logger.error(f"Invalid bbox {geometry}: {error_msg} - skipping")
    return normalized_geom


def _shape_to_geojson(shape):
    """Convert a Shapely geometry to a GeoJSON-like dict."""
    if shape is None or shape.is_empty:
        return None

    geojson = shapely_mapping(shape)
    normalized = _normalize_geojson_geometry(geojson)
    return normalized


def process_geometry(geometry):
    """Process geometry for Elasticsearch with validation."""
    if not geometry:
        return None

    try:
        if isinstance(geometry, str):
            original_value = geometry
            geometry = geometry.strip()

            # Check if it's an ENVELOPE format (case insensitive)
            envelope_match = re.match(
                r"ENVELOPE\(([-\d.]+)\s*,\s*([-\d.]+)\s*,\s*([-\d.]+)\s*,\s*([-\d.]+)\)",
                geometry,
                re.IGNORECASE,
            )
            if envelope_match:
                # Extract coordinates from ENVELOPE(minx,maxx,maxy,miny)
                minx, maxx, maxy, miny = map(float, envelope_match.groups())

                # Normalize and validate the envelope coordinates
                normalized_geom, error_msg = _normalize_envelope(minx, maxx, maxy, miny)

                if normalized_geom is None:
                    logger.error(f"Invalid envelope {geometry}: {error_msg} - skipping")
                    return None

                return normalized_geom

            # Handle simple comma-delimited centroid/bbox strings
            bbox_geom = _convert_bbox_string_to_envelope(geometry)
            if bbox_geom:
                return bbox_geom

            # Handle simple coordinate pair (lat, lon)
            coordinate_pair_match = re.match(
                r"^\s*([-+]?\d*\.?\d+)\s*,\s*([-+]?\d*\.?\d+)\s*$", geometry
            )
            if coordinate_pair_match:
                lat = float(coordinate_pair_match.group(1))
                lon = float(coordinate_pair_match.group(2))
                # Store as Point in lon, lat order for GeoJSON/ES
                point_coords = [lon, lat]
                if not _is_valid_point(point_coords):
                    logger.warning(f"Invalid point coordinates: {point_coords} - skipping")
                    return None
                return {"type": "Point", "coordinates": point_coords}

            # Try to parse as WKT using Shapely
            try:
                shapely_geom = shapely_wkt.loads(geometry)
            except Exception:
                shapely_geom = None

            if shapely_geom:
                geojson = _shape_to_geojson(shapely_geom)
                if geojson:
                    return geojson

            # Try to parse as JSON
            try:
                geometry = json.loads(geometry)
            except json.JSONDecodeError:
                logger.debug(f"Unable to parse geometry string '{original_value}' as JSON/WKT")
                return None

        if isinstance(geometry, dict):
            normalized = _normalize_geojson_geometry(geometry)
            return normalized

    except Exception as e:
        logger.warning(f"Error processing geometry {geometry}: {e} - skipping")
        return None


def _normalize_envelope(minx, maxx, maxy, miny):
    """
    Normalize and validate envelope coordinates.

    Returns:
        tuple: (geometry_dict, error_msg) where geometry_dict is None if invalid
    """
    # Check for valid coordinate ranges first
    if not (-180 <= minx <= 180) or not (-180 <= maxx <= 180):
        return None, f"X coordinates out of range: minx={minx}, maxx={maxx}"
    if not (-90 <= miny <= 90) or not (-90 <= maxy <= 90):
        return None, f"Y coordinates out of range: miny={miny}, maxy={maxy}"

    # Auto-correct inverted coordinates
    if minx > maxx:
        logger.debug(f"Auto-correcting inverted X coordinates: swapping {minx} and {maxx}")
        minx, maxx = maxx, minx

    if miny > maxy:
        logger.debug(f"Auto-correcting inverted Y coordinates: swapping {miny} and {maxy}")
        miny, maxy = maxy, miny

    # Check if this is actually a point (zero-area envelope)
    if minx == maxx and miny == maxy:
        logger.debug(f"Converting zero-area envelope to POINT: ({minx}, {miny})")
        return {"type": "point", "coordinates": [minx, miny]}, None

    # Check for very thin envelopes (essentially lines or near-points)
    epsilon = 1e-6  # ~0.11 meters at equator

    if abs(maxx - minx) < epsilon and abs(maxy - miny) < epsilon:
        # Both dimensions tiny - treat as point
        center_x = (minx + maxx) / 2
        center_y = (miny + maxy) / 2
        logger.debug(f"Converting near-point envelope to POINT: ({center_x}, {center_y})")
        return {"type": "point", "coordinates": [center_x, center_y]}, None

    elif abs(maxx - minx) < epsilon:
        # Width tiny but height OK - expand width slightly
        center_x = (minx + maxx) / 2
        minx = center_x - epsilon
        maxx = center_x + epsilon
        logger.debug(f"Expanding thin envelope width: {minx} to {maxx}")

    elif abs(maxy - miny) < epsilon:
        # Height tiny but width OK - expand height slightly
        center_y = (miny + maxy) / 2
        miny = center_y - epsilon
        maxy = center_y + epsilon
        logger.debug(f"Expanding thin envelope height: {miny} to {maxy}")

    # Create valid polygon from normalized envelope
    return {
        "type": "polygon",
        "coordinates": [
            [
                [minx, maxy],  # top-left
                [maxx, maxy],  # top-right
                [maxx, miny],  # bottom-right
                [minx, miny],  # bottom-left
                [minx, maxy],  # close the ring
            ]
        ],
    }, None


def _is_valid_point(coords):
    """Validate point coordinates."""
    if not isinstance(coords, (list, tuple)) or len(coords) < 2:
        return False

    lon, lat = coords[0], coords[1]
    return -180 <= lon <= 180 and -90 <= lat <= 90


def _is_valid_polygon_coordinates(coords, geom_type):
    """Validate polygon or multipolygon coordinates."""
    if not coords:
        return False

    if geom_type == "polygon":
        return _is_valid_single_polygon(coords)
    elif geom_type == "multipolygon":
        return all(_is_valid_single_polygon(poly) for poly in coords)

    return False


def _is_valid_single_polygon(coords):
    """Validate a single polygon coordinates."""
    if not isinstance(coords, list) or len(coords) == 0:
        return False

    # Check the outer ring
    outer_ring = coords[0]
    if not isinstance(outer_ring, list) or len(outer_ring) < 4:
        return False

    # Check that the polygon is closed (first and last points are the same)
    if outer_ring[0] != outer_ring[-1]:
        return False

    # Check that all coordinates are valid
    for coord in outer_ring:
        if not _is_valid_point(coord):
            return False

    # Check for minimum area (at least 3 non-collinear points)
    if len(outer_ring) < 4:  # 3 unique points + closing point
        return False

    # Check for collinear points (simplified check)
    if _are_points_collinear(outer_ring[:3]):
        return False

    return True


def _are_points_collinear(points):
    """Check if three points are collinear."""
    if len(points) < 3:
        return False

    p1, p2, p3 = points[0], points[1], points[2]

    # Calculate the cross product to check if points are collinear
    # If cross product is 0, points are collinear
    cross_product = (p2[0] - p1[0]) * (p3[1] - p1[1]) - (p2[1] - p1[1]) * (p3[0] - p1[0])

    # Use a small epsilon for floating point comparison
    return abs(cross_product) < 1e-10


async def perform_individual_indexing(resources_data, index_name, batch_size=100):
    """Index resources individually (slower but 100% reliable).

    Args:
        resources_data: List of processed resource dicts ready to index
        index_name: Elasticsearch index name
        batch_size: Number of docs to index before logging progress
    """
    total_resources = len(resources_data)
    total_indexed = 0
    total_errors = 0
    failure_logger = _get_failure_logger()

    logger.info(f"Starting individual indexing of {total_resources} resources...")

    for i, resource_dict in enumerate(resources_data):
        try:
            doc_id = resource_dict.get("id")

            # Index this document individually
            response = await es.index(
                index=index_name,
                id=doc_id,
                document=resource_dict,
                refresh=False,  # Don't refresh after each doc (performance)
            )

            # Check if successful
            if response.get("result") in ["created", "updated"]:
                total_indexed += 1
            else:
                logger.warning(f"Unexpected result for {doc_id}: {response.get('result')}")
                # Log a structured line with the full response for post-mortem
                try:
                    failure_logger.info(
                        json.dumps(
                            {
                                "id": doc_id,
                                "index": index_name,
                                "stage": "index",
                                "reason": "unexpected_result",
                                "response": response,
                            }
                        )
                    )
                except Exception:
                    # Best-effort logging; do not fail indexing due to logging errors
                    pass
                total_errors += 1

            # Log progress every batch_size documents
            if (i + 1) % batch_size == 0:
                logger.info(
                    f"Progress: {total_indexed}/{total_resources} indexed "
                    f"({total_errors} errors, {i + 1} processed)"
                )

        except Exception as e:
            total_errors += 1
            doc_id = resource_dict.get("id", "unknown")
            logger.error(f"Error indexing document {doc_id}: {str(e)}")
            # Persist failure details for later triage
            try:
                failure_logger.info(
                    json.dumps(
                        {
                            "id": doc_id,
                            "index": index_name,
                            "stage": "index",
                            "reason": "exception",
                            "error": str(e),
                        }
                    )
                )
            except Exception:
                pass
            # Continue with next document instead of failing completely

    # Final refresh to make all indexed documents searchable
    logger.info("Refreshing index to make all documents searchable...")
    if total_indexed > 0:
        try:
            await es.indices.refresh(index=index_name)
            logger.info("Index refresh complete")
        except Exception as e:
            logger.warning(f"Failed to refresh index: {e}")

    logger.info(
        f"Individual indexing complete: {total_indexed} successful, "
        f"{total_errors} errors out of {total_resources} total resources"
    )

    return {"indexed": total_indexed, "errors": total_errors, "total": total_resources}


async def reindex_resources():
    """Reindex all resources from PostgreSQL into Elasticsearch with the new mapping."""
    index_name = os.getenv("ELASTICSEARCH_INDEX", "btaa_geospatial_api")

    try:
        # Delete the existing index if it exists
        if await es.indices.exists(index=index_name):
            logger.info(f"Deleting existing index {index_name}")
            await es.indices.delete(index=index_name)

        # Initialize Elasticsearch with the new mapping
        from .client import init_elasticsearch

        await init_elasticsearch()

        # Process items in chunks
        chunk_size = 1000  # Adjust this based on your needs
        offset = 0
        total_processed = 0  # number of items fetched/attempted this run
        total_indexed = 0
        total_errors = 0

        while True:
            # Fetch a chunk of documents from the database
            query = resources.select().offset(offset).limit(chunk_size)
            chunk = await database.fetch_all(query)

            if not chunk:
                break  # No more items to process

            # Prepare resources for this chunk
            processed_resources = await prepare_bulk_data(chunk, index_name)

            if processed_resources:
                # Index this chunk
                result = await perform_individual_indexing(processed_resources, index_name)
                total_processed += result.get("total", len(processed_resources))
                total_indexed += result.get("indexed", 0)
                total_errors += result.get("errors", 0)
                logger.info(
                    f"Progress: attempted={total_processed}, "
                    f"indexed={total_indexed}, errors={total_errors}"
                )

            offset += chunk_size

        if total_processed > 0:
            return {
                "attempted": total_processed,
                "indexed": total_indexed,
                "errors": total_errors,
                "message": (
                    f"Indexing finished: {total_indexed} indexed, "
                    f"{total_errors} errors out of {total_processed} attempted"
                ),
            }
        return {"message": "No resources to index", "attempted": 0, "indexed": 0, "errors": 0}

    except Exception as e:
        logger.error(f"Error during reindexing: {str(e)}", exc_info=True)
        raise


def _update_bbox_metrics(processed_dict, geometry):
    """Compute numeric bbox metrics (minx, maxx, miny, maxy, diagonal_km)."""
    if not geometry or not isinstance(geometry, dict):
        return
    coords = geometry.get("coordinates")
    if not coords:
        return

    def _walk(c, acc):
        if isinstance(c, (list, tuple)):
            if len(c) == 2 and all(isinstance(v, (int, float)) for v in c):
                x, y = float(c[0]), float(c[1])
                acc[0] = min(acc[0], x)
                acc[1] = min(acc[1], y)
                acc[2] = max(acc[2], x)
                acc[3] = max(acc[3], y)
            else:
                for v in c:
                    _walk(v, acc)

    acc = [float("inf"), float("inf"), float("-inf"), float("-inf")]
    _walk(coords, acc)
    minx, miny, maxx, maxy = acc
    if (
        not math.isfinite(minx)
        or not math.isfinite(miny)
        or not math.isfinite(maxx)
        or not math.isfinite(maxy)
    ):
        return

    processed_dict["bbox_minx"] = minx
    processed_dict["bbox_maxx"] = maxx
    processed_dict["bbox_miny"] = miny
    processed_dict["bbox_maxy"] = maxy

    # Approximate diagonal length in km for later scoring heuristics
    avg_lat = (miny + maxy) / 2.0
    dx = maxx - minx
    dy = maxy - miny
    lat_km = dy * 111.0
    lon_km = dx * 111.0 * abs(math.cos(math.radians(avg_lat)))
    processed_dict["bbox_diagonal_km"] = math.sqrt(lat_km**2 + lon_km**2)
