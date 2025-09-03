import logging
import os
from typing import Optional

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
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
from app.services.cache_service import cached_endpoint
from app.services.download_service import DownloadService
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
LIST_CACHE_TTL = int(os.getenv("LIST_CACHE_TTL", 43200))  # 12 hours


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
