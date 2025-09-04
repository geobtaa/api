import logging
from typing import Optional

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.api.v1.utils import create_jsonapi_response, process_resource, sanitize_for_json
from app.services.cache_service import cached_endpoint
from app.services.search_service import SearchService
from db.config import DATABASE_URL
from db.models import resources

logger = logging.getLogger(__name__)

router = APIRouter()

# Cache TTL configuration in seconds
SEARCH_CACHE_TTL = int(3600)  # 1 hour
SUGGEST_CACHE_TTL = int(7200)  # 2 hours

# Create async engine and session for search results processing
engine = create_async_engine(DATABASE_URL)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


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

        # Extract resource IDs and scores from search results
        resource_data = []
        for item in results.get("data", []):
            try:
                # Extract the resource ID and score from the search result
                resource_id = None
                score = None

                if "attributes" in item and isinstance(item["attributes"], dict):
                    if "attributes" in item["attributes"]:
                        # Nested structure: item.attributes.attributes.id
                        resource_id = item["attributes"]["attributes"].get("id")
                        score = item["attributes"].get("score")
                    else:
                        # Direct structure: item.attributes.id
                        resource_id = item["attributes"].get("id")
                        score = item.get("score")
                else:
                    # Fallback: item.id
                    resource_id = item.get("id")
                    score = item.get("score")

                if resource_id:
                    resource_data.append({"id": resource_id, "score": score})
            except Exception as e:
                logger.error(f"Error extracting resource data from search result: {str(e)}")
                continue

        # Load full resource data from database using the same logic as /resources
        processed_resources = []
        async with async_session() as session:
            for resource_info in resource_data:
                try:
                    resource_id = resource_info["id"]
                    score = resource_info["score"]

                    # Query the database for the full resource
                    query = select(resources).where(resources.c.id == resource_id)
                    result = await session.execute(query)
                    row = result.fetchone()

                    if row:
                        # Convert to dict and sanitize datetime objects
                        resource_dict = sanitize_for_json(dict(row._mapping))
                        logger.info(f"Processing search result resource: {resource_id}")

                        # Process the resource using the same logic as other endpoints
                        # First process without field mapping to preserve database field names
                        # for internal processing
                        resource_object = await process_resource(
                            resource_dict, session, apply_field_mapping=False
                        )

                        # Now apply field mapping to the final attributes for proper OGM field names
                        # in API response
                        from app.services.ogm_field_mapper import OGMFieldMapper

                        if "attributes" in resource_object:
                            resource_object["attributes"] = OGMFieldMapper.map_resource_fields(
                                resource_object["attributes"]
                            )

                        # Add the Elasticsearch score to the resource's meta section
                        if score is not None:
                            if "meta" not in resource_object:
                                resource_object["meta"] = {}

                            # Reorder meta fields: @context, @type, score, ui
                            reordered_meta = {}

                            # Add standard JSON-LD fields first
                            if "@context" in resource_object["meta"]:
                                reordered_meta["@context"] = resource_object["meta"]["@context"]
                            if "@type" in resource_object["meta"]:
                                reordered_meta["@type"] = resource_object["meta"]["@type"]

                            # Add score prominently
                            reordered_meta["score"] = score

                            # Add UI section last
                            if "ui" in resource_object["meta"]:
                                reordered_meta["ui"] = resource_object["meta"]["ui"]

                            resource_object["meta"] = reordered_meta

                        processed_resources.append(resource_object)
                        logger.info(f"Successfully processed search result resource {resource_id}")
                    else:
                        logger.warning(f"Resource {resource_id} not found in database")
                except Exception as e:
                    logger.error(
                        f"Error processing search result resource {resource_id}: {str(e)}",
                        exc_info=True,
                    )
                    continue

        # Extract pagination info from existing meta
        pages_info = results.get("meta", {}).get("pages", {})
        total_count = pages_info.get("total_count", 0)
        total_pages = pages_info.get("total_pages", 0)
        current_page = page

        # Build pagination links
        base_url = str(request.url).split("?")[0]  # Get base URL without query params
        params = {}
        if q:
            params["q"] = q
        if sort:
            params["sort"] = sort
        if per_page != 10:  # Only include if not default
            params["per_page"] = per_page

        # Build query string for links
        query_parts = []
        for key, value in params.items():
            query_parts.append(f"{key}={value}")
        query_string = "&".join(query_parts) if query_parts else ""

        # Create pagination links
        links = {"self": f"{base_url}?page={current_page}&{query_string}".rstrip("&")}

        if current_page < total_pages:
            links["next"] = f"{base_url}?page={current_page + 1}&{query_string}".rstrip("&")

        if current_page > 1:
            links["prev"] = f"{base_url}?page={current_page - 1}&{query_string}".rstrip("&")

        if total_pages > 1:
            links["first"] = f"{base_url}?page=1&{query_string}".rstrip("&")
            links["last"] = f"{base_url}?page={total_pages}&{query_string}".rstrip("&")

        # Build comprehensive meta information
        meta = {
            "totalCount": total_count,
            "totalPages": total_pages,
            "currentPage": current_page,
            "perPage": per_page,
            "query": q,
            "sort": sort,
            "query_time": results.get("meta", {}).get("query_time", {}),
            "spelling_suggestions": results.get("meta", {}).get("spelling_suggestions", []),
        }

        # Create JSON:API compliant response
        request_url = str(request.url) if request else None
        jsonapi_response = create_jsonapi_response(
            data=processed_resources, request_url=request_url, callback=callback
        )

        # Add our custom links and meta BEFORE the data section
        jsonapi_response["links"] = links
        jsonapi_response["meta"] = meta

        # Add included data (facets/aggregations) from search results
        if "included" in results:
            jsonapi_response["included"] = results["included"]

        # Reorder the response to put meta before data
        reordered_response = {
            "jsonapi": jsonapi_response["jsonapi"],
            "links": jsonapi_response["links"],
            "meta": jsonapi_response["meta"],
            "data": jsonapi_response["data"],
        }

        # Add included if it exists
        if "included" in jsonapi_response:
            reordered_response["included"] = jsonapi_response["included"]

        # Return the response
        return JSONResponse(content=reordered_response)
    except Exception as e:
        logger.error(f"Error performing search: {str(e)}", exc_info=True)
        return JSONResponse(content={"error": str(e)}, status_code=500)


@router.get("/suggest")
@cached_endpoint(ttl=SUGGEST_CACHE_TTL)
async def suggest(
    q: str = Query(..., description="Search query for suggestions"),
    callback: Optional[str] = Query(None, description="JSONP callback name"),
    request: Request = None,
):
    """Get search suggestions."""
    try:
        search_service = SearchService()
        suggestions = await search_service.suggest(q)

        # Create JSON:API compliant response
        request_url = str(request.url) if request else None
        jsonapi_response = create_jsonapi_response(
            data=suggestions.get("data", []), request_url=request_url, callback=callback
        )

        return JSONResponse(content=jsonapi_response)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)
