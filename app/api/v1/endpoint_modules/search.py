import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.api.v1.utils import create_jsonapi_response, process_resource_optimized, sanitize_for_json
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
    page: int = Query(1, ge=1, description="Page number (minimum: 1)"),
    per_page: int = Query(10, ge=1, le=100, description="Resources per page (1-100)"),
    sort: Optional[str] = Query(
        None, description="Sort option (relevance, year_desc, year_asc, title_asc, title_desc)"
    ),
    search_field: Optional[str] = Query(None, description="Search field (all_fields, etc.)"),
    fields: Optional[str] = Query(None, description="Comma-separated list of fields to return"),
    meta: bool = Query(True, description="Include per-resource meta block (default: true)"),
    format: Optional[str] = Query(None, description="Response format (json, jsonp)"),
    callback: Optional[str] = Query(None, description="JSONP callback name"),
):
    """Search resources."""
    import time

    start_time = time.time()

    try:
        logger.info(
            f"🔍 Starting search request: q='{q}', page={page}, per_page={per_page}, sort='{sort}'"
        )

        # Step 1: Call SearchService
        step1_start = time.time()
        search_service = SearchService()
        logger.info(f"⏱️  Step 1: Creating SearchService - {time.time() - step1_start:.3f}s")

        step2_start = time.time()
        results = await search_service.search(
            q=q,
            page=page,
            limit=per_page,
            sort=sort,
            search_fields=search_field,
            request_query_params=str(request.query_params),
            callback=callback,
        )
        step2_duration = time.time() - step2_start
        logger.info(f"⏱️  Step 2: Elasticsearch search completed - {step2_duration:.3f}s")

        # Debug: Log the structure of results
        logger.info(f"🔍 Search results type: {type(results)}")
        if isinstance(results, dict):
            logger.info(f"🔍 Search results keys: {list(results.keys())}")
        elif isinstance(results, list):
            logger.info(f"🔍 Search results length: {len(results)}")
            if results:
                logger.info(f"🔍 First result type: {type(results[0])}")
                if isinstance(results[0], dict):
                    logger.info(f"🔍 First result keys: {list(results[0].keys())}")

        if step2_duration > 2.0:
            logger.warning(f"⚠️  Elasticsearch search took {step2_duration:.3f}s - this is slow!")

        # Step 3: Sanitize and extract resource data
        step3_start = time.time()
        sanitized_results = sanitize_for_json(results)

        # Extract resource IDs and scores from search results
        resource_data = []
        data_count = len(sanitized_results.get("data", []))
        logger.info(f"📊 Found {data_count} search results to process")

        for i, item in enumerate(sanitized_results.get("data", [])):
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
                    if i < 3:  # Log first few for debugging
                        logger.debug(f"  📝 Extracted: {resource_id} (score: {score})")
            except Exception as e:
                logger.error(f"Error extracting resource data from search result: {str(e)}")
                continue

        step3_duration = time.time() - step3_start
        logger.info(f"⏱️  Step 3: Data extraction completed - {step3_duration:.3f}s")
        logger.info(f"📋 Extracted {len(resource_data)} valid resource IDs")

        # Step 4: Database queries and resource processing (likely bottleneck)
        step4_start = time.time()
        logger.info(f"🗄️  Starting database queries for {len(resource_data)} resources...")

        # OPTIMIZATION: Pre-fetch Allmaps data for all resources in a single query
        async def fetch_allmaps_data_batch(session, resource_ids):
            """Fetch Allmaps data for multiple resources in a single query."""
            try:
                from sqlalchemy import select

                from db.models import resource_allmaps

                # Query all resources at once
                query = select(resource_allmaps).where(
                    resource_allmaps.c.resource_id.in_(resource_ids)
                )
                result = await session.execute(query)
                rows = result.fetchall()

                # Create a lookup dictionary
                allmaps_lookup = {}
                for row in rows:
                    allmaps_dict = dict(row._mapping)
                    resource_id = allmaps_dict["resource_id"]
                    allmaps_lookup[resource_id] = {
                        "ui_allmaps_id": allmaps_dict.get("allmaps_id"),
                        "ui_allmaps_annotated": allmaps_dict.get("annotated"),
                        "ui_allmaps_manifest_uri": allmaps_dict.get("iiif_manifest_uri"),
                    }

                logger.info(f"📊 Pre-fetched Allmaps data for {len(allmaps_lookup)} resources")
                return allmaps_lookup
            except Exception as e:
                logger.error(f"Error fetching Allmaps data batch: {e}")
                return {}

        # OPTIMIZATION: Pre-fetch all resource data in a single query
        async def fetch_resources_batch(session, resource_ids):
            """Fetch all resource data in a single database query."""
            try:
                # Query all resources at once
                query = select(resources).where(resources.c.id.in_(resource_ids))
                result = await session.execute(query)
                rows = result.fetchall()

                # Create a lookup dictionary
                resources_lookup = {}
                for row in rows:
                    resource_dict = sanitize_for_json(dict(row._mapping))
                    resource_id = resource_dict["id"]
                    resources_lookup[resource_id] = resource_dict

                logger.info(f"📊 Pre-fetched resource data for {len(resources_lookup)} resources")
                return resources_lookup
            except Exception as e:
                logger.error(f"Error fetching resources batch: {e}")
                return {}

        # Process resources in parallel for much better performance
        async def process_single_resource(resource_info, session, allmaps_lookup, resources_lookup):
            """Process a single resource asynchronously using pre-fetched data."""
            resource_start = time.time()
            try:
                resource_id = resource_info["id"]
                score = resource_info["score"]

                # OPTIMIZATION: Use pre-fetched resource data instead of individual database query
                resource_dict = resources_lookup.get(resource_id)
                if not resource_dict:
                    logger.warning(f"❌ Resource {resource_id} not found in pre-fetched data")
                    return None

                # No more individual database queries - data is already in memory!
                db_query_duration = 0.0  # Set to 0 since we're not querying individually

                # OPTIMIZATION: Use pre-fetched Allmaps data instead of individual queries
                allmaps_attributes = allmaps_lookup.get(resource_id, {})

                # Process the resource with optimized Allmaps handling
                process_start = time.time()
                resource_object = await process_resource_optimized(
                    resource_dict, allmaps_attributes, apply_field_mapping=False
                )
                # Apply fields filter if requested (after mapping to OGM names)
                if fields and isinstance(resource_object, dict):
                    try:
                        from app.services.ogm_field_mapper import OGMFieldMapper

                        if "attributes" in resource_object and isinstance(
                            resource_object["attributes"], dict
                        ):
                            mapped_attrs = OGMFieldMapper.map_resource_fields(
                                resource_object["attributes"]
                            )
                            requested = [f.strip() for f in fields.split(",") if f.strip()]
                            if "id" not in requested:
                                requested.append("id")
                            filtered_attrs = {
                                k: v for k, v in mapped_attrs.items() if k in requested
                            }
                            # Ensure id remains top-level only
                            filtered_attrs.pop("id", None)
                            resource_object["attributes"] = filtered_attrs
                    except Exception as e:
                        logger.error(f"Error applying fields filter: {e}")
                process_duration = time.time() - process_start

                if process_duration > 0.5:  # Log slow processing
                    logger.warning(
                        f"🐌 Slow resource processing for {resource_id}: {process_duration:.3f}s"
                    )

                # Now apply field mapping to the final attributes for proper OGM field names
                # in API response
                from app.services.ogm_field_mapper import OGMFieldMapper

                if "attributes" in resource_object:
                    resource_object["attributes"] = OGMFieldMapper.map_resource_fields(
                        resource_object["attributes"]
                    )

                # Add the Elasticsearch score to the resource's meta section (if requested)
                if meta:
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
                else:
                    # Remove per-resource meta if not requested
                    if "meta" in resource_object:
                        resource_object.pop("meta", None)

                resource_duration = time.time() - resource_start
                if process_duration > 0.5:  # Log slow ones
                    logger.info(
                        f"✅ Processed {resource_id} in {resource_duration:.3f}s "
                        f"(DB: {db_query_duration:.3f}s, Process: {process_duration:.3f}s)"
                    )
                else:
                    logger.debug(f"✅ Processed {resource_id} in {resource_duration:.3f}s")

                return resource_object
            except Exception as e:
                resource_duration = time.time() - resource_start
                logger.error(
                    f"💥 Error processing search result resource {resource_id} "
                    f"after {resource_duration:.3f}s: {str(e)}",
                    exc_info=True,
                )
                return None

        # Process all resources in parallel
        processed_resources = []
        async with async_session() as session:
            # OPTIMIZATION: Pre-fetch Allmaps data for all resources
            resource_ids = [r["id"] for r in resource_data]
            allmaps_lookup = await fetch_allmaps_data_batch(session, resource_ids)

            # OPTIMIZATION: Pre-fetch all resource data in a single query
            resources_lookup = await fetch_resources_batch(session, resource_ids)

            # Create tasks for all resources
            tasks = [
                process_single_resource(resource_info, session, allmaps_lookup, resources_lookup)
                for resource_info in resource_data
            ]

            # Execute all tasks concurrently
            task_results = await asyncio.gather(*tasks, return_exceptions=True)

            # Filter out None results and exceptions
            for i, result in enumerate(task_results):
                if isinstance(result, Exception):
                    logger.error(f"Task {i} failed with exception: {result}")
                elif result is not None:
                    processed_resources.append(result)

        step4_duration = time.time() - step4_start
        logger.info(
            f"⏱️  Step 4: Database queries and resource processing completed - {step4_duration:.3f}s"
        )
        logger.info(
            f"📦 Successfully processed {len(processed_resources)}/{len(resource_data)} resources"
        )

        if step4_duration > 5.0:
            logger.warning(
                f"⚠️  Database processing took {step4_duration:.3f}s - this is very slow!"
            )

        # Step 5: Build final response
        step5_start = time.time()
        logger.info("🔧 Building final response...")

        # Extract pagination info from existing meta
        pages_info = results.get("meta", {}).get("pages", {})
        total_count = pages_info.get("total_count", 0)
        total_pages = pages_info.get("total_pages", 0)
        current_page = page

        # Build pagination links using strong parameters (Rails-style whitelisting)
        from app.api.v1.strong_params import SEARCH_ALLOWED_PARAMS
        from app.api.v1.utils import create_pagination_links

        links = create_pagination_links(
            request,
            current_page,
            total_pages,
            pagination_type="page",
            allowed_params=SEARCH_ALLOWED_PARAMS,
        )

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
        jsonapi_start = time.time()
        request_url = str(request.url) if request else None
        jsonapi_response = create_jsonapi_response(
            data=processed_resources, request_url=request_url, callback=callback
        )
        jsonapi_duration = time.time() - jsonapi_start
        logger.debug(f"📄 JSON:API response creation took {jsonapi_duration:.3f}s")

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

        step5_duration = time.time() - step5_start
        logger.info(f"⏱️  Step 5: Response building completed - {step5_duration:.3f}s")

        # Final timing summary
        total_duration = time.time() - start_time
        logger.info(f"🎯 Total search request completed in {total_duration:.3f}s")
        logger.info("📊 Performance breakdown:")
        logger.info(
            f"   - Elasticsearch: {step2_duration:.3f}s "
            f"({step2_duration / total_duration * 100:.1f}%)"
        )
        logger.info(
            f"   - Data extraction: {step3_duration:.3f}s "
            f"({step3_duration / total_duration * 100:.1f}%)"
        )
        logger.info(
            f"   - Database processing: {step4_duration:.3f}s "
            f"({step4_duration / total_duration * 100:.1f}%)"
        )
        logger.info(
            f"   - Response building: {step5_duration:.3f}s "
            f"({step5_duration / total_duration * 100:.1f}%)"
        )

        if total_duration > 5.0:
            logger.warning(f"⚠️  Total search request took {total_duration:.3f}s - this is slow!")

        # Return the response
        return JSONResponse(content=reordered_response)
    except Exception as e:
        total_duration = time.time() - start_time
        logger.error(
            f"💥 Search request failed after {total_duration:.3f}s: {str(e)}", exc_info=True
        )
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
