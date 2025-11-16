import json
import logging
import os
from typing import Optional

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import select

from app.api.v1.utils import (
    create_jsonapi_response,
    create_response,
    process_resource,
    sanitize_for_json,
)
from app.services.cache_service import cached_endpoint
from app.services.distribution_repository import fetch_distribution_context
from app.services.image_service import ImageService
from app.services.link_service import LinkService
from app.services.ogm_field_mapper import OGMFieldMapper
from app.services.relationship_service import RelationshipService
from app.services.spatial_facet_service import SpatialFacetService
from app.services.static_map_service import StaticMapService
from app.tasks.static_maps import generate_static_map
from db.config import DATABASE_URL
from db.models import resources

# Load environment variables from .env file
load_dotenv()


def filter_resource_fields(resource_dict: dict, fields_param: Optional[str]) -> dict:
    """
    Filter resource fields based on the fields parameter.
    Always includes 'id' field even if not specified.

    Args:
        resource_dict: The resource dictionary to filter
        fields_param: Comma-separated string of field names to include

    Returns:
        Filtered resource dictionary
    """
    if not fields_param:
        return resource_dict

    # Parse the fields parameter
    requested_fields = [field.strip() for field in fields_param.split(",") if field.strip()]

    # Always include 'id' field
    if "id" not in requested_fields:
        requested_fields.append("id")

    # Filter the resource dictionary to only include requested fields
    filtered_resource = {}
    for field in requested_fields:
        if field in resource_dict:
            filtered_resource[field] = resource_dict[field]

    return filtered_resource


router = APIRouter()

logger = logging.getLogger(__name__)

# Create async engine and session with connection pool settings
engine = create_async_engine(
    DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=1800,  # Recycle connections after 30 minutes
    pool_pre_ping=True,  # Verify connections before using them
)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

base_url = os.getenv("APPLICATION_URL", "http://localhost:8000/api/v1/")

# Cache TTL configuration in seconds
RESOURCE_CACHE_TTL = int(os.getenv("RESOURCE_CACHE_TTL", 86400))  # 24 hours
LIST_CACHE_TTL = int(os.getenv("LIST_CACHE_TTL", 43200))  # 12 hours


@router.get("/resources/")
@cached_endpoint(ttl=LIST_CACHE_TTL)
async def list_resources(
    skip: int = 0,
    limit: int = 10,
    fields: Optional[str] = Query(None, description="Comma-separated list of fields to return"),
    callback: Optional[str] = Query(None, description="JSONP callback name"),
    format: Optional[str] = Query(None, description="Response format (json, jsonp)"),
    request: Request = None,
):
    try:
        async with async_session() as session:
            query = select(resources).offset(skip).limit(limit)
            logger.info(f"Executing query: {query}")
            result = await session.execute(query)
            results = result.fetchall()  # Get full rows instead of scalars
            logger.info(f"Found {len(results)} resources")

            processed_resources = []
            for row in results:
                try:
                    logger.info(f"Processing resource: {row}")
                    # Convert to dict and sanitize datetime objects
                    resource_dict = sanitize_for_json(dict(row._mapping))
                    logger.info(f"Resource dict: {resource_dict}")

                    # Apply field filtering if fields parameter is provided
                    if fields:
                        resource_dict = filter_resource_fields(resource_dict, fields)
                        logger.info(f"Filtered resource dict: {resource_dict}")

                    # Process the resource using the shared function
                    jsonapi_resource = await process_resource(resource_dict, session)
                    processed_resources.append(jsonapi_resource)
                    logger.info(f"Successfully processed resource {resource_dict['id']}")
                except Exception as e:
                    logger.error(f"Error processing resource: {str(e)}", exc_info=True)
                    continue

            logger.info(f"Returning {len(processed_resources)} processed resources")

        # Create JSON:API compliant response
        request_url = str(request.url) if request else None
        jsonapi_response = create_jsonapi_response(
            data=processed_resources, request_url=request_url, callback=callback
        )

        return JSONResponse(content=jsonapi_response)
    except Exception as e:
        logger.error(f"Error in list_resources: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/resources/{id}")
@cached_endpoint(ttl=RESOURCE_CACHE_TTL)
async def get_resource(
    id: str,
    fields: Optional[str] = Query(None, description="Comma-separated list of fields to return"),
    callback: Optional[str] = Query(None, description="JSONP callback name"),
    format: Optional[str] = Query(None, description="Response format (json, jsonp)"),
    request: Request = None,
):
    """Get a single resource by ID."""
    try:
        # Get resource data directly from database (not Elasticsearch)
        # to ensure clean Aardvark fields
        async with async_session() as session:
            query = select(resources).where(resources.c.id == id)
            result = await session.execute(query)
            row = result.fetchone()

            if not row:
                return JSONResponse(content={"error": "Resource not found"}, status_code=404)

            # Convert to dict and sanitize for JSON serialization
            resource_dict = sanitize_for_json(dict(row._mapping))
            resource_dict["id"] = id  # Ensure ID is set

            # Apply field filtering if fields parameter is provided
            if fields:
                resource_dict = filter_resource_fields(resource_dict, fields)
                logger.info(f"Filtered resource dict: {resource_dict}")

            # Process the resource using the shared function (this will add Allmaps to meta.ui)
            jsonapi_resource = await process_resource(resource_dict, session)

        # Create JSON:API compliant response
        request_url = str(request.url) if request else None
        jsonapi_response = create_jsonapi_response(
            data=jsonapi_resource, request_url=request_url, callback=callback
        )

        return JSONResponse(content=jsonapi_response)
    except HTTPException:
        # Re-raise HTTP exceptions to maintain their status code
        raise
    except Exception as e:
        logger.error(f"Error getting resource {id}: {str(e)}", exc_info=True)
        return JSONResponse(content={"error": str(e)}, status_code=500)


@router.get("/resources/{id}/distributions")
@cached_endpoint(ttl=RESOURCE_CACHE_TTL)
async def get_resource_distributions(
    id: str,
    callback: Optional[str] = Query(None, description="JSONP callback name"),
    request: Request = None,
):
    """Get all distributions for a resource."""
    try:
        # First check if the resource exists
        async with async_session() as session:
            resource_query = select(resources.c.id).where(resources.c.id == id)
            resource_result = await session.execute(resource_query)
            resource_row = resource_result.fetchone()

            if not resource_row:
                return JSONResponse(content={"error": "Resource not found"}, status_code=404)

            # Get distributions with distribution type information
            distributions_query = text("""
                SELECT 
                    rd.id,
                    rd.resource_id,
                    rd.url,
                    rd.label,
                    rd.position,
                    rd.created_at,
                    rd.updated_at,
                    rd.import_distribution_id,
                    dt.id as distribution_type_id,
                    dt.name as distribution_type_name,
                    dt.distribution_type,
                    dt.distribution_uri,
                    dt.note as distribution_note
                FROM resource_distributions rd
                JOIN distribution_types dt ON rd.distribution_type_id = dt.id
                WHERE rd.resource_id = :resource_id
                ORDER BY rd.position ASC, rd.created_at ASC
            """)

            result = await session.execute(distributions_query, {"resource_id": id})
            distributions = result.fetchall()

            # Convert to list of dicts and sanitize
            distributions_list = []
            for dist in distributions:
                dist_dict = sanitize_for_json(dict(dist._mapping))
                distributions_list.append(dist_dict)

            # Create JSON:API compliant response
            request_url = str(request.url) if request else None
            jsonapi_response = create_jsonapi_response(
                data={
                    "type": "distributions",
                    "id": id,
                    "attributes": {
                        "distributions": distributions_list,
                        "count": len(distributions_list),
                    },
                },
                request_url=request_url,
                callback=callback,
            )

            return JSONResponse(content=jsonapi_response)

    except Exception as e:
        logger.error(f"Error getting distributions for resource {id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/resources/{id}/ogm")
async def get_resource_ogm(
    id: str,
    fields: Optional[str] = Query(None, description="Comma-separated list of fields to return"),
    callback: Optional[str] = Query(None, description="JSONP callback name"),
):
    """Get just the OpenGeoMetadata Aardvark record for a resource by ID."""
    try:
        async with async_session() as session:
            query = select(resources).where(resources.c.id == id)
            result = await session.execute(query)
            row = result.fetchone()
            if not row:
                return JSONResponse(content={"error": "Resource not found"}, status_code=404)

            # Convert to dict and sanitize datetime objects
            resource_dict = sanitize_for_json(dict(row._mapping))

            # Map database column names to official Aardvark field names
            aardvark_attributes = OGMFieldMapper.map_resource_fields(resource_dict)

            # Filter out null values and empty arrays
            aardvark_record = {}
            for key, value in aardvark_attributes.items():
                if value is not None and value != "":
                    # Handle empty arrays
                    if isinstance(value, list) and len(value) == 0:
                        continue
                    # Handle arrays with only None/empty values
                    if isinstance(value, list) and all(
                        item is None or item == "" for item in value
                    ):
                        continue
                    aardvark_record[key] = value

            # Apply field filtering if fields parameter is provided
            if fields:
                aardvark_record = filter_resource_fields(aardvark_record, fields)
                logger.info(f"Filtered OGM record: {aardvark_record}")

            # Rebuild dct_references_s from resource_distributions for OGM output
            try:
                distribution_context = await fetch_distribution_context(id)
                legacy_refs = distribution_context.legacy_reference_payload
                if legacy_refs:
                    aardvark_record["dct_references_s"] = json.dumps(legacy_refs)
            except Exception:
                pass

            # Return just the cleaned attributes (the Aardvark record)
            return create_response(aardvark_record, callback)
    except HTTPException:
        # Re-raise HTTP exceptions to maintain their status code
        raise
    except Exception as e:
        logger.error(f"Error getting Aardvark record for resource {id}: {str(e)}", exc_info=True)
        return JSONResponse(content={"error": str(e)}, status_code=500)


@router.get("/resources/{id}/links")
async def get_resource_links(
    id: str,
    callback: Optional[str] = Query(None, description="JSONP callback name"),
):
    """Get all links for a resource."""
    return await LinkService.get_resource_links(id)


@router.get("/resources/{id}/relationships")
async def get_resource_relationships(
    id: str,
    callback: Optional[str] = Query(None, description="JSONP callback name"),
):
    """Get all relationships for a resource."""
    return await RelationshipService.get_resource_relationships(id)


@router.get("/resources/{id}/spatial_facets")
async def get_resource_spatial_facets(
    id: str,
    callback: Optional[str] = Query(None, description="JSONP callback name"),
    debug: bool = Query(False, description="Include overlap ratios in results"),
    request: Request = None,
):
    """Get spatial hierarchical facets (country, state, county) and bounding box for a resource."""
    try:
        # Fetch the resource data first using the proper async session
        async with async_session() as session:
            query = select(resources.c.id, resources.c.dcat_bbox).where(resources.c.id == id)
            result = await session.execute(query)
            row = result.fetchone()

            if not row:
                # Return empty response for nonexistent resource
                response_data = {"id": id, "type": "spatial_facets", "attributes": {}}
                request_url = str(request.url) if request else None
                return create_jsonapi_response(response_data, request_url, callback)

            # Convert to dict
            resource_dict = dict(row._mapping)

            # Get spatial facets using the SpatialFacetService with the resource data
            service = SpatialFacetService(resource_dict)
            spatial_facets = await service.get_spatial_facets_with_wof_ids(session, debug=debug)

            # Prepare attributes with dcat_bbox first, then spatial facets
            attributes = {}
            if resource_dict.get("dcat_bbox"):
                attributes["dcat_bbox"] = resource_dict["dcat_bbox"]
            # Add spatial facets after dcat_bbox
            attributes.update(spatial_facets)

            # Create JSON:API compliant response
            response_data = {"id": id, "type": "spatial_facets", "attributes": attributes}

            request_url = str(request.url) if request else None
            return create_jsonapi_response(response_data, request_url, callback)

    except Exception as e:
        logger.error(f"Error getting spatial facets for resource {id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Error retrieving spatial facets: {str(e)}"
        ) from e


@router.get("/resources/{id}/static-map")
@cached_endpoint(ttl=RESOURCE_CACHE_TTL)
async def get_resource_static_map(
    id: str,
    request: Request = None,
):
    """Get a static map image for a resource based on its locn_geometry (or dcat_bbox as fallback)."""
    try:
        # First check if the resource exists and has geometry
        async with async_session() as session:
            query = select(resources.c.id, resources.c.locn_geometry, resources.c.dcat_bbox).where(
                resources.c.id == id
            )
            result = await session.execute(query)
            row = result.fetchone()

            if not row:
                return JSONResponse(content={"error": "Resource not found"}, status_code=404)

            resource_dict = dict(row._mapping)
            # Prefer locn_geometry over dcat_bbox
            geometry = resource_dict.get("locn_geometry") or resource_dict.get("dcat_bbox")

            if not geometry:
                return JSONResponse(
                    content={"error": "Resource has no geometry"}, status_code=404
                )

        # Check if map already exists
        map_service = StaticMapService()
        map_path = map_service.get_map_path(id)

        if map_path and map_path.exists():
            # Return the map image (display inline in browser)
            # Remove filename parameter to prevent download, browser will display inline
            return FileResponse(
                str(map_path),
                media_type="image/png",
                headers={"Content-Disposition": "inline"},
            )

        # Map doesn't exist, trigger Celery task to generate it
        try:
            generate_static_map.delay(id)
            logger.info(f"Triggered static map generation for resource {id}")
        except Exception as e:
            logger.error(f"Error triggering static map generation for resource {id}: {e}")

        # Return 202 Accepted while map is being generated
        return JSONResponse(
            content={
                "status": "processing",
                "message": "Static map is being generated. Please try again in a few moments.",
            },
            status_code=202,
        )

    except HTTPException:
        # Re-raise HTTP exceptions to maintain their status code
        raise
    except Exception as e:
        logger.error(f"Error getting static map for resource {id}: {str(e)}", exc_info=True)
        return JSONResponse(content={"error": str(e)}, status_code=500)


@router.get("/resources/{id}/summaries")
async def get_resource_summaries(
    id: str,
    callback: Optional[str] = Query(None, description="JSONP callback name"),
    request: Request = None,
):
    """Get all summaries for a resource."""
    try:
        # Query the database for summaries
        async with async_session() as session:
            query = text("""
                SELECT * FROM resource_ai_enrichments 
                WHERE resource_id = :resource_id 
                ORDER BY created_at DESC
            """)
            result = await session.execute(query, {"resource_id": id})
            summaries = result.fetchall()

            # Convert to list of dicts and sanitize
            summaries_list = [sanitize_for_json(dict(summary)) for summary in summaries]

            # Create JSON:API compliant response
            request_url = str(request.url) if request else None
            jsonapi_response = create_jsonapi_response(
                data={"type": "summaries", "id": id, "attributes": {"summaries": summaries_list}},
                request_url=request_url,
                callback=callback,
            )

            return JSONResponse(content=jsonapi_response)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/resources/{id}/thumbnail")
async def get_resource_thumbnail(
    id: str,
    callback: Optional[str] = Query(None, description="JSONP callback name"),
    debug: bool = Query(False, description="Include debug details about thumbnail resolution"),
):
    """Get the current thumbnail URL (or placeholder) for a resource."""
    try:
        # Fetch resource to access references and other metadata
        async with async_session() as session:
            query = select(resources).where(resources.c.id == id)
            result = await session.execute(query)
            row = result.fetchone()

            if not row:
                return JSONResponse(content={"error": "Resource not found"}, status_code=404)

            resource_dict = sanitize_for_json(dict(row._mapping))

        # Compute thumbnail URL using ImageService
        distribution_context = await fetch_distribution_context(id)
        image_service = ImageService(resource_dict, distribution_context=distribution_context)
        thumbnail_url = image_service.get_thumbnail_url()

        # Ensure placeholder when none available
        if not thumbnail_url:
            application_url = os.getenv("APPLICATION_URL", "http://localhost:8000").rstrip("/")
            thumbnail_url = f"{application_url}/api/v1/thumbnails/placeholder"

        is_placeholder = "/api/v1/thumbnails/placeholder" in thumbnail_url

        response_payload = {
            "id": id,
            "thumbnail_url": thumbnail_url,
            "placeholder": is_placeholder,
        }

        # Optional debug block with rich insight into detection and caching
        if debug:
            import hashlib

            # Determine raw source URL without network
            source_url = image_service._get_thumbnail_source_url()
            standardized_source = (
                image_service._standardize_iiif_url(source_url) if source_url else None
            )

            # If manifest, try to resolve to an image (network call; 2s timeout inside service)
            resolved_url = None
            if (
                source_url
                and isinstance(source_url, str)
                and source_url.endswith(("/manifest", "manifest.json"))
            ):
                try:
                    resolved_url = image_service.get_iiif_manifest_thumbnail(source_url)
                    if resolved_url:
                        resolved_url = image_service._standardize_iiif_url(resolved_url)
                except Exception:
                    resolved_url = None

            # Compute the hash key used for caching based on the queued URL (standardized_source)
            image_hash = (
                hashlib.sha256((standardized_source or "").encode()).hexdigest()
                if standardized_source
                else None
            )
            cache_key = f"image:{image_hash}" if image_hash else None

            cache_exists = None
            try:
                if cache_key:
                    cache_exists = bool(image_service.image_cache.exists(cache_key))
            except Exception:
                cache_exists = None

            response_payload["debug"] = {
                "source_url": source_url,
                "standardized_source": standardized_source,
                "resolved_url": resolved_url,
                "image_hash": image_hash,
                "cache_key": cache_key,
                "cache_exists": cache_exists,
            }

        return create_response(response_payload, callback)
    except Exception as e:
        logger.error(f"Error getting thumbnail for resource {id}: {str(e)}", exc_info=True)
        return JSONResponse(content={"error": str(e)}, status_code=500)


@router.get("/resources/{id}/viewer")
async def get_resource_viewer(
    id: str,
    embed: bool = Query(False, description="Embedded mode for iframe usage"),
):
    """Get an HTML page with the embedded OGM viewer for a specific resource."""
    try:
        # First check if the resource exists
        async with async_session() as session:
            query = select(resources).where(resources.c.id == id)
            result = await session.execute(query)
            row = result.fetchone()

            if not row:
                raise HTTPException(status_code=404, detail="Resource not found")

        # Build the record URL for the viewer
        base_url = os.getenv("APPLICATION_URL", "http://localhost:8000")
        record_url = f"{base_url}/api/v1/resources/{id}/ogm"

        # Create the HTML content
        html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OGM Viewer - Resource {id}</title>
    <style>
        body {{
            margin: 0;
            padding: 0;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        }}
        .viewer-container {{
            width: 100vw;
            height: 100vh;
        }}
        {".viewer-container { height: 600px; }" if embed else ""}
    </style>
</head>
<body>
    <div class="viewer-container">
        <ogm-viewer 
            record-url="{record_url}"
            >
        </ogm-viewer>
    </div>
    
    <!-- Load the OGM Viewer web component -->
    <script type="module" src="https://unpkg.com/ogm-viewer"></script>
</body>
</html>
"""

        # Create response with iframe-friendly headers
        response = HTMLResponse(content=html_content)

        # Allow iframe embedding from any domain
        response.headers["X-Frame-Options"] = "ALLOWALL"
        response.headers["Content-Security-Policy"] = "frame-ancestors *"

        # Use credentialless COEP for maximum compatibility with parent pages
        # This allows embedding in pages with strict COEP policies
        response.headers["Cross-Origin-Embedder-Policy"] = "credentialless"

        return response
    except HTTPException:
        # Re-raise HTTPExceptions (like 404) without modification
        raise
    except Exception as e:
        logger.error(f"Error creating viewer page for resource {id}: {str(e)}", exc_info=True)
        return JSONResponse(content={"error": str(e)}, status_code=500)


