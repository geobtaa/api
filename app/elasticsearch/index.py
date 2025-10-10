import json
import logging
import os
import re

from dotenv import load_dotenv

from db.database import database
from db.models import resources

from .client import es

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)


async def index_resources():
    """Index all resources from PostgreSQL into Elasticsearch."""
    index_name = os.getenv("ELASTICSEARCH_INDEX", "btaa_ogm_api")

    if await es.indices.exists(index=index_name):
        await es.indices.delete(index=index_name)

    from .client import init_elasticsearch

    await init_elasticsearch()

    resource_rows = await database.fetch_all(resources.select())
    bulk_data = await prepare_bulk_data(resource_rows, index_name)

    if bulk_data:
        return await perform_bulk_indexing(bulk_data, index_name)

    return {"message": "No resources to index"}


async def prepare_bulk_data(resources, index_name):
    """Prepare resources for bulk indexing."""
    bulk_data = []
    for resource in resources:
        resource_dict = await process_resource(dict(resource))
        bulk_data.append({"index": {"_index": index_name, "_id": resource_dict["id"]}})
        bulk_data.append(resource_dict)
    return bulk_data


async def process_resource(resource_dict):
    """Process a single resource for indexing."""
    processed_dict = {}

    for key, value in resource_dict.items():
        if isinstance(value, (list, tuple)):
            processed_dict[key] = list(value)
        elif key == "dct_references_s" and value:
            try:
                processed_dict[key] = json.loads(value)
            except json.JSONDecodeError:
                processed_dict[key] = value
        # Handle geometry fields
        elif key in ["locn_geometry", "dcat_bbox", "dcat_centroid"]:
            # Store original string value
            processed_dict[f"{key}_original"] = value
            # Convert to GeoJSON for Elasticsearch using validated processing
            if value:
                processed_geometry = process_geometry(value)
                if processed_geometry:
                    # Ensure type is capitalized for consistency
                    if "type" in processed_geometry:
                        processed_geometry["type"] = processed_geometry["type"].capitalize()
                    processed_dict[key] = processed_geometry
                else:
                    # If geometry processing failed, store None to avoid indexing invalid geometries
                    processed_dict[key] = None
            else:
                processed_dict[key] = None
        else:
            processed_dict[key] = value

    # Add summaries to the document
    processed_dict["ai_summaries"] = await get_resource_summaries(processed_dict["id"])

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


def process_geometry(geometry):
    """Process geometry for Elasticsearch with validation."""
    if not geometry:
        return None

    try:
        # Try to parse as GeoJSON
        if isinstance(geometry, str):
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

            # Try to parse as JSON
            try:
                geometry = json.loads(geometry)
            except json.JSONDecodeError:
                return None

        # Handle different geometry types
        if isinstance(geometry, dict):
            geom_type = geometry.get("type", "").lower()
            if geom_type == "point":
                coords = geometry.get("coordinates", [0, 0])
                if not _is_valid_point(coords):
                    logger.warning(f"Invalid point coordinates: {coords} - skipping")
                    return None
                return {"type": "point", "coordinates": coords}
            elif geom_type in ["polygon", "multipolygon"]:
                coords = geometry.get("coordinates")
                if not _is_valid_polygon_coordinates(coords, geom_type):
                    logger.warning(f"Invalid {geom_type} coordinates: {coords} - skipping")
                    return None
                return {"type": geom_type, "coordinates": coords}
            else:
                return None
        else:
            return None

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
        return {
            "type": "point",
            "coordinates": [minx, miny]
        }, None

    # Check for very thin envelopes (essentially lines or near-points)
    epsilon = 1e-6  # ~0.11 meters at equator
    
    if abs(maxx - minx) < epsilon and abs(maxy - miny) < epsilon:
        # Both dimensions tiny - treat as point
        center_x = (minx + maxx) / 2
        center_y = (miny + maxy) / 2
        logger.debug(f"Converting near-point envelope to POINT: ({center_x}, {center_y})")
        return {
            "type": "point",
            "coordinates": [center_x, center_y]
        }, None
    
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
        "coordinates": [[
            [minx, maxy],  # top-left
            [maxx, maxy],  # top-right
            [maxx, miny],  # bottom-right
            [minx, miny],  # bottom-left
            [minx, maxy],  # close the ring
        ]]
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


async def perform_bulk_indexing(bulk_data, index_name, bulk_size=100):
    """Perform bulk indexing in smaller chunks.
    
    Args:
        bulk_data: List of alternating action/document pairs
        index_name: Elasticsearch index name
        bulk_size: Number of OPERATIONS (not items) per chunk
    """
    # Each bulk operation consists of 2 items (action + document)
    # So we need to step by bulk_size * 2 to avoid splitting operations
    chunk_step = bulk_size * 2
    
    total_operations = len(bulk_data) // 2
    total_indexed = 0
    total_errors = 0
    
    for i in range(0, len(bulk_data), chunk_step):
        chunk = bulk_data[i : i + chunk_step]
        
        # Skip incomplete chunks (shouldn't happen, but be safe)
        if len(chunk) % 2 != 0:
            logger.warning(f"Skipping incomplete bulk chunk at offset {i}")
            continue
        
        try:
            # Perform the bulk operation for the current chunk
            response = await es.bulk(operations=chunk, index=index_name, refresh=False)
            
            # Check for errors in the response
            error_count = 0  # Initialize for this chunk
            success_count = 0  # Actually count successes
            
            if response.get("items"):
                for item in response.get("items", []):
                    # Each item is a dict with a single key (the operation type)
                    for op_type, op_result in item.items():
                        status = op_result.get("status", 0)
                        if status >= 200 and status < 300:
                            success_count += 1
                        else:
                            error_count += 1
                            total_errors += 1
                            # Log first few errors in detail
                            if error_count <= 10:
                                logger.error(
                                    f"Bulk indexing error for ID {op_result.get('_id')}: "
                                    f"Status {status}, "
                                    f"Error: {op_result.get('error')}"
                                )
                
                if error_count > 10:
                    logger.error(f"... and {error_count - 10} more errors in this chunk")
                
                if error_count > 0:
                    logger.error(f"Chunk had {error_count} failed operations out of {len(chunk)//2}")
            else:
                # No items in response - this is a problem
                logger.error(f"Bulk response has no items! Response keys: {list(response.keys())}")
                error_count = len(chunk) // 2
                total_errors += error_count
            
            total_indexed += success_count
            
            if (i // chunk_step) % 10 == 0:  # Log every 10 chunks
                logger.info(
                    f"Progress: {total_indexed}/{total_operations} operations "
                    f"({total_errors} errors)"
                )
                
        except Exception as e:
            logger.error(f"Exception during bulk indexing chunk at offset {i}: {str(e)}", exc_info=True)
            total_errors += len(chunk) // 2
            # Continue with next chunk instead of failing completely
    
    # Final refresh to make all indexed documents searchable
    if total_indexed > 0:
        try:
            await es.indices.refresh(index=index_name)
        except Exception as e:
            logger.warning(f"Failed to refresh index: {e}")
    
    logger.info(
        f"Bulk indexing complete: {total_indexed} successful, "
        f"{total_errors} errors out of {total_operations} total operations"
    )
    
    return {"indexed": total_indexed, "errors": total_errors, "total": total_operations}


async def reindex_resources():
    """Reindex all resources from PostgreSQL into Elasticsearch with the new mapping."""
    index_name = os.getenv("ELASTICSEARCH_INDEX", "btaa_geometadata_api")

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
        total_processed = 0

        while True:
            # Fetch a chunk of documents from the database
            query = resources.select().offset(offset).limit(chunk_size)
            chunk = await database.fetch_all(query)

            if not chunk:
                break  # No more items to process

            # Prepare bulk data for this chunk
            bulk_data = await prepare_bulk_data(chunk, index_name)

            if bulk_data:
                # Index this chunk
                await perform_bulk_indexing(bulk_data, index_name)
                total_processed += len(chunk)
                logger.info(f"Indexed {total_processed} resources so far")

            offset += chunk_size

        if total_processed > 0:
            return {"message": f"Successfully indexed {total_processed} resources"}
        return {"message": "No resources to index"}

    except Exception as e:
        logger.error(f"Error during reindexing: {str(e)}", exc_info=True)
        raise
