import logging
import os
from typing import Optional

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import select

from app.api.v1.utils import (
    create_jsonapi_response,
    process_resource,
    sanitize_for_json,
)
from app.services.allmaps_service import AllmapsService
from app.services.cache_service import cached_endpoint
from app.services.search_service import SearchService
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
    request: Request = None,
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

            # Extract the resource data and process it using the shared function
            resource_data = response["data"]["attributes"]
            resource_data["id"] = id  # Ensure ID is set

            # Process the resource using the shared function
            jsonapi_resource = await process_resource(resource_data, session)

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


@router.get("/resources/")
@cached_endpoint(ttl=LIST_CACHE_TTL)
async def list_resources(
    skip: int = 0,
    limit: int = 10,
    callback: Optional[str] = Query(None, description="JSONP callback name"),
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
