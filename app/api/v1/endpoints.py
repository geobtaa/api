import logging
import os
from typing import Optional

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import select

from app.api.v1.utils import (
    add_thumbnail_url,
    create_response,
    sanitize_for_json,
)
from app.services.allmaps_service import AllmapsService
from app.services.cache_service import (
    cached_endpoint,
)
from app.services.download_service import DownloadService
from app.services.image_service import ImageService
from app.services.search_service import SearchService
from app.services.viewer_service import ViewerService
from db.config import DATABASE_URL
from db.models import resources

# Load environment variables from .env file
load_dotenv()

router = APIRouter()

logger = logging.getLogger(__name__)

# Create async engine and session
engine = create_async_engine(DATABASE_URL)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

base_url = os.getenv("APPLICATION_URL", "http://localhost:8000/api/v1/")

# Cache TTL configuration in seconds
RESOURCE_CACHE_TTL = int(os.getenv("RESOURCE_CACHE_TTL", 86400))  # 24 hours
SEARCH_CACHE_TTL = int(os.getenv("SEARCH_CACHE_TTL", 3600))  # 1 hour
SUGGEST_CACHE_TTL = int(os.getenv("SUGGEST_CACHE_TTL", 7200))  # 2 hours
LIST_CACHE_TTL = int(os.getenv("LIST_CACHE_TTL", 43200))  # 12 hours


@router.get("")
async def api_root():
    """Return basic API information including version."""
    return JSONResponse(
        content={
            "api": "BTAA Geodata API",
            "version": "0.1.0",
            "description": (
                "API for accessing geospatial data from the Big Ten Academic Alliance Geoportal"
            ),
            "endpoints": ["/resources", "/search", "/suggest"],
        }
    )


@router.get("/resources/{id}")
@cached_endpoint(ttl=RESOURCE_CACHE_TTL)
async def get_resource(
    id: str,
    callback: Optional[str] = Query(None, description="JSONP callback name"),
):
    """Get a single resource by ID."""
    try:
        search_service = SearchService()
        response = await search_service.get_resource(id)
        if not response:
            return JSONResponse(content={"error": "Resource not found"}, status_code=404)

        # Sanitize the resource data for JSON serialization
        response = sanitize_for_json(response)

        # Add Allmaps data
        logger.info(f"Processing resource data: {response}")
        async with async_session() as session:
            allmaps_service = AllmapsService(
                {"id": id, "attributes": response["data"]["attributes"]}
            )
            allmaps_attributes = await allmaps_service.get_allmaps_attributes(session)
            logger.info(f"Got Allmaps attributes: {allmaps_attributes}")
            # Update the attributes dictionary
            response["data"]["attributes"].update(allmaps_attributes)

        return create_response(response, callback)
    except HTTPException:
        # Re-raise HTTP exceptions to maintain their status code
        raise
    except Exception as e:
        logger.error(f"Error getting resource {id}: {str(e)}", exc_info=True)
        return JSONResponse(content={"error": str(e)}, status_code=500)


@router.get("/resources/")
@cached_endpoint(ttl=LIST_CACHE_TTL)
async def list_resources(
    skip: int = 0,
    limit: int = 10,
    callback: Optional[str] = Query(None, description="JSONP callback name"),
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
                    resource_dict = add_thumbnail_url(resource_dict)

                    # Use ViewerService to get viewer attributes
                    viewer_service = ViewerService(resource_dict)
                    viewer_attributes = viewer_service.get_viewer_attributes()
                    logger.info(f"Viewer attributes: {viewer_attributes}")

                    # Use DownloadService to get download options
                    download_service = DownloadService(resource_dict)
                    ui_downloads = download_service.get_download_options()
                    logger.info(f"Download options: {ui_downloads}")

                    # Get Allmaps attributes
                    allmaps_service = AllmapsService(resource_dict)
                    allmaps_attributes = await allmaps_service.get_allmaps_attributes(session)
                    logger.info(f"Allmaps attributes: {allmaps_attributes}")

                    # Create the attributes dictionary
                    attributes = {
                        **resource_dict,
                        "ui_citation": resource_dict.get("ui_citation"),
                        "ui_thumbnail_url": resource_dict.get("ui_thumbnail_url"),
                        "ui_viewer_endpoint": viewer_attributes.get("ui_viewer_endpoint"),
                        "ui_viewer_geometry": viewer_attributes.get("ui_viewer_geometry"),
                        "ui_viewer_protocol": viewer_attributes.get("ui_viewer_protocol"),
                        "ui_downloads": ui_downloads,
                    }

                    # Add viewer attributes
                    for key, value in viewer_attributes.items():
                        if key not in attributes:
                            attributes[key] = value

                    # Add Allmaps attributes
                    for key, value in allmaps_attributes.items():
                        if key not in attributes:
                            attributes[key] = value

                    processed_resources.append(
                        {
                            "type": "resource",
                            "id": str(resource_dict["id"]),
                            "attributes": attributes,
                        }
                    )
                    logger.info(f"Successfully processed resource {resource_dict['id']}")
                except Exception as e:
                    logger.error(f"Error processing resource: {str(e)}", exc_info=True)
                    continue

            logger.info(f"Returning {len(processed_resources)} processed resources")
            return create_response({"data": processed_resources}, callback)
    except Exception as e:
        logger.error(f"Error in list_resources: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/search")
@cached_endpoint(ttl=SEARCH_CACHE_TTL)
async def search(
    request: Request,
    q: Optional[str] = Query(None, description="Search query"),
    page: int = Query(1, description="Page number"),
    per_page: int = Query(10, description="Resources per page"),
    sort: Optional[str] = Query(
        None, description="Sort option (relevance, year_desc, year_asc, title_asc, title_desc)"
    ),
    callback: Optional[str] = Query(None, description="JSONP callback name"),
):
    """Search resources."""
    try:
        search_service = SearchService()
        results = await search_service.search(
            q=q,
            page=page,
            limit=per_page,
            sort=sort,
            request_query_params=str(request.query_params),
            callback=callback,
        )

        # Sanitize the results for JSON serialization
        results = sanitize_for_json(results)

        # Create the response
        response = create_response(results, callback)

        # Return the response
        return response
    except Exception as e:
        logger.error(f"Error performing search: {str(e)}", exc_info=True)
        return JSONResponse(content={"error": str(e)}, status_code=500)


@router.get("/suggest")
@cached_endpoint(ttl=SUGGEST_CACHE_TTL)
async def suggest(
    q: str = Query(..., description="Search query for suggestions"),
    callback: Optional[str] = Query(None, description="JSONP callback name"),
):
    """Get search suggestions."""
    try:
        search_service = SearchService()
        suggestions = await search_service.suggest(q)
        return create_response(suggestions, callback)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


@router.get("/thumbnails/{image_hash}")
async def get_thumbnail(image_hash: str):
    """Serve a cached thumbnail image."""
    try:
        # Create service without resource (we only need cache access)
        image_service = ImageService({})
        image_data = await image_service.get_cached_image(image_hash)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    if not image_data:
        raise HTTPException(status_code=404, detail="Image not found")

    return Response(
        content=image_data,
        media_type="image/jpeg",
        headers={"Cache-Control": "public, max-age=31536000"},  # Cache for 1 year
    )


@router.get("/resources/{id}/summaries")
async def get_resource_summaries(
    id: str,
    callback: Optional[str] = Query(None, description="JSONP callback name"),
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

            # Create response
            response_data = {
                "data": {"type": "summaries", "id": id, "attributes": {"summaries": summaries_list}}
            }

            return create_response(response_data, callback)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
