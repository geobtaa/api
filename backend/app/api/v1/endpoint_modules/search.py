import json
import logging
from typing import Annotated, Optional

from fastapi import APIRouter, Body, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.api.v1.advanced_search_utils import validate_adv_q
from app.api.v1.strong_params import FACET_ALLOWED_PARAMS
from app.api.v1.utils import (
    create_jsonapi_response,
    create_pagination_links,
    filter_empty_values,
    process_resource_optimized,
    sanitize_for_json,
)
from app.elasticsearch.search import (
    generate_facet_apply_template,
    get_facet_aggregation_config,
    get_facet_values,
    get_search_criteria,
    process_facet_response,
)
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


async def _handle_search(request: Request, params: dict) -> JSONResponse:
    """Shared search executor and response builder for GET and POST.

    Expects params to contain: q, page, per_page, sort, search_field, fields,
    facets, meta, callback, request_query_params (for GET only), include_filters,
    exclude_filters, fq, adv_q.
    """

    # Defaults
    q = params.get("q")
    page = int(params.get("page", 1))
    per_page = int(params.get("per_page", 10))
    sort = params.get("sort")
    search_field = params.get("search_field")
    fields = params.get("fields")
    facets = params.get("facets")
    meta = params.get("meta", True)
    callback = params.get("callback")
    request_query_params = params.get("request_query_params")
    include_filters = params.get("include_filters")
    exclude_filters = params.get("exclude_filters")
    fq = params.get("fq")
    adv_q = params.get("adv_q")

    # Validate adv_q if provided
    if adv_q is not None:
        adv_q = validate_adv_q(adv_q)

    # Step 1: Call SearchService
    search_service = SearchService()
    results = await search_service.search(
        q=q,
        page=page,
        limit=per_page,
        sort=sort,
        search_fields=search_field,
        request_query_params=request_query_params,
        callback=callback,
        facets=facets,
        include_filters=include_filters,
        exclude_filters=exclude_filters,
        fq_direct=fq,
        adv_q=adv_q,
    )

    # Step 2: Extract resource IDs and scores
    sanitized_results = sanitize_for_json(results)
    result_obj = sanitized_results if isinstance(sanitized_results, dict) else {}
    resource_data = []
    for item in sanitized_results.get("data", []):
        rid = None
        score = None
        overlap = None
        if isinstance(item, dict):
            rid = (
                item.get("id")
                or item.get("attributes", {}).get("id")
                or item.get("attributes", {}).get("attributes", {}).get("id")
            )
            # Be careful not to treat 0.0 as falsy; only fall back on None
            score = item.get("score")
            if score is None:
                score = item.get("attributes", {}).get("score")

            overlap = item.get("bbox_overlap_ratio")
            if overlap is None:
                overlap = item.get("attributes", {}).get("bbox_overlap_ratio")
        if rid:
            resource_data.append({"id": rid, "score": score, "bbox_overlap_ratio": overlap})

    # Step 3: Batch fetch resource data
    lookup = {}
    if resource_data:
        try:
            async with async_session() as session:
                query = select(resources).where(
                    resources.c.id.in_([r["id"] for r in resource_data])
                )
                result = await session.execute(query)
                rows = result.fetchall()
                lookup = {
                    dict(row._mapping)["id"]: sanitize_for_json(dict(row._mapping)) for row in rows
                }
        except Exception as e:
            # If database query fails (e.g., connection pool closed), log and continue
            # with empty lookup. This allows the endpoint to return empty results rather
            # than crashing.
            logger.warning(f"Database query failed in search endpoint: {str(e)}")
            lookup = {}

    # Process resources (initialize outside the if block to avoid UnboundLocalError)
    processed_resources = []

    if resource_data:
        for rd in resource_data:
            d = lookup.get(rd["id"]) or {}
            obj = await process_resource_optimized(d, {}, apply_field_mapping=False)
            # obj["attributes"] is already nested with "ogm" and "b1g" structure
            # from create_jsonapi_resource
            attrs = obj.get("attributes", {})

            # Attach ES scoring and overlap ratio info into per-resource meta for debugging
            if rd.get("score") is not None:
                obj.setdefault("meta", {})
                obj["meta"]["score"] = rd["score"]
            if rd.get("bbox_overlap_ratio") is not None:
                obj.setdefault("meta", {})
                obj["meta"]["bbox_overlap_ratio"] = rd["bbox_overlap_ratio"]

            if isinstance(fields, str) and fields.strip():
                # Handle field filtering for nested attributes structure
                requested = [f.strip() for f in fields.split(",") if f.strip()]
                if "id" not in requested:
                    requested.append("id")

                # Filter nested attributes (ogm and b1g)
                filtered_attrs = {}
                if "ogm" in attrs:
                    filtered_ogm = {k: v for k, v in attrs["ogm"].items() if k in requested}
                    if filtered_ogm:
                        filtered_attrs["ogm"] = filtered_ogm
                if "b1g" in attrs:
                    filtered_b1g = {k: v for k, v in attrs["b1g"].items() if k in requested}
                    if filtered_b1g:
                        filtered_attrs["b1g"] = filtered_b1g

                obj["attributes"] = filtered_attrs
            else:
                # Use nested attributes as-is
                obj["attributes"] = attrs

            # Filter out empty arrays and empty strings from nested attributes
            # filter_empty_values already handles nested dicts recursively
            obj["attributes"] = filter_empty_values(obj["attributes"])
            if not meta and "meta" in obj:
                obj.pop("meta", None)
            processed_resources.append(obj)

    # Step 4: Build JSON:API response
    pages_info = result_obj.get("meta", {}).get("pages", {})
    total_count = pages_info.get("total_count", 0)
    total_pages = pages_info.get("total_pages", 0)

    from app.api.v1.strong_params import SEARCH_ALLOWED_PARAMS

    links = create_pagination_links(
        request,
        page,
        total_pages,
        pagination_type="page",
        allowed_params=SEARCH_ALLOWED_PARAMS,
    )

    meta_block = {
        "totalCount": int(total_count),
        "totalPages": int(total_pages),
        "currentPage": page,
        "perPage": per_page,
        "query": q,
        "sort": sort,
        "queryTime": results.get("queryTime", {}),
        "spellingSuggestions": results.get("meta", {}).get("spellingSuggestions", []),
    }

    # Build response with desired key order: jsonapi -> links -> meta -> data -> included
    base = create_jsonapi_response(data=[], request_url=str(request.url))
    response = {
        "jsonapi": base.get("jsonapi", {}),
        "links": links,
        "meta": meta_block,
        "data": processed_resources,
    }
    if isinstance(result_obj, dict) and "included" in result_obj:
        response["included"] = result_obj["included"]

    return JSONResponse(content=sanitize_for_json(response))


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
    facets: Optional[str] = Query(None, description="Comma-separated list of facets to return"),
    meta: bool = Query(True, description="Include per-resource meta block (default: true)"),
    format: Optional[str] = Query(None, description="Response format (json, jsonp)"),
    callback: Optional[str] = Query(None, description="JSONP callback name"),
    adv_q: Optional[str] = Query(
        None,
        description=(
            "JSON array of advanced query clauses. "
            "Each clause: {'op': 'AND|OR|NOT', 'f': 'dct_title_s', 'q': 'Iowa'}"
        ),
    ),
):
    """Search resources."""

    import time

    start_time = time.time()

    try:
        logger.info(
            f"🔍 Starting search request: q='{q}', page={page}, per_page={per_page}, sort='{sort}'"
        )

        # Parse adv_q from JSON string if provided
        parsed_adv_q = None
        if adv_q:
            try:
                parsed_adv_q = json.loads(adv_q)
            except json.JSONDecodeError as e:
                return JSONResponse(
                    content={"error": f"Invalid JSON in adv_q parameter: {str(e)}"},
                    status_code=400,
                )

        # Get the raw query string from the request scope before FastAPI parses it
        # This preserves bracket notation that FastAPI might filter from request.url.query
        raw_query_string = (
            request.scope.get("query_string", b"").decode("utf-8")
            if isinstance(request.scope.get("query_string"), bytes)
            else request.scope.get("query_string", "")
        )
        query_string = (
            raw_query_string
            if raw_query_string
            else (request.url.query if request.url.query else "")
        )
        logger.info(
            f"Search GET: raw_query_string length={len(raw_query_string)}, "
            f"query_string length={len(query_string)}, "
            f"sample={query_string[:300]}"
        )

        # Extract filters manually to ensure they are passed correctly
        from app.services.search_service import SearchService

        search_service = SearchService()
        include_filters, exclude_filters = search_service.extract_new_style_filters(query_string)

        return await _handle_search(
            request,
            {
                "q": q,
                "page": page,
                "per_page": per_page,
                "sort": sort,
                "search_field": search_field,
                "fields": fields,
                "facets": facets,
                "meta": meta,
                "callback": callback,
                "request_query_params": query_string,
                "adv_q": parsed_adv_q,
                "include_filters": include_filters,
                "exclude_filters": exclude_filters,
            },
        )
    except Exception as e:
        total_duration = time.time() - start_time
        logger.error(
            f"💥 Search request failed after {total_duration:.3f}s: {str(e)}", exc_info=True
        )
        return JSONResponse(content={"error": str(e)}, status_code=500)


@cached_endpoint(ttl=SEARCH_CACHE_TTL)
@router.post("/search")
async def search_post(
    request: Request,
    payload: Annotated[
        dict,
        Body(
            ...,
            description="Search body. Same fields as GET but in JSON.",
            examples=[
                {
                    "q": "seattle",
                    "include_filters": {"dct_spatial_sm": ["Washington"]},
                    "exclude_filters": {"dct_spatial_sm": ["Iowa"]},
                },
                {
                    "adv_q": [
                        {"op": "AND", "f": "dct_title_s", "q": "Iowa"},
                        {"op": "NOT", "f": "dct_title_s", "q": "Wisconsin"},
                        {"op": "AND", "f": "dct_description_sm", "q": "Water"},
                    ]
                },
            ],
        ),
    ],
):
    """POST variant of search. Accepts JSON body.

    Supported keys:
      - q, page, per_page, sort, search_field, fields, facets, meta
      - include_filters, exclude_filters, fq (object of field->values)
      - adv_q (array of query clauses with op, f, q)
    """

    # Extract parameters with defaults matching GET
    q = payload.get("q")
    page = int(payload.get("page", 1))
    per_page = int(payload.get("per_page", 10))
    sort = payload.get("sort")
    search_field = payload.get("search_field")
    fields = payload.get("fields")
    facets = payload.get("facets")
    meta = payload.get("meta", True)
    callback = payload.get("callback")
    adv_q = payload.get("adv_q")

    include_filters = payload.get("include_filters")
    exclude_filters = payload.get("exclude_filters")
    fq = payload.get("fq")

    # Reuse shared helper
    try:
        return await _handle_search(
            request,
            {
                "q": q,
                "page": page,
                "per_page": per_page,
                "sort": sort,
                "search_field": search_field,
                "fields": fields,
                "facets": facets,
                "meta": meta,
                "callback": callback,
                "include_filters": include_filters,
                "exclude_filters": exclude_filters,
                "fq": fq,
                "adv_q": adv_q,
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


@router.get("/search/facets/{facet_name}")
@cached_endpoint(ttl=SEARCH_CACHE_TTL)
async def get_facet(
    facet_name: str,
    request: Request,
    q: Optional[str] = Query(None, description="Search query to filter resultset"),
    page: int = Query(1, ge=1, description="Page number (minimum: 1)"),
    per_page: int = Query(10, ge=1, le=100, description="Facet values per page (1-100)"),
    sort: Optional[str] = Query(
        "count_desc",
        description="Sort option: count_desc, count_asc, alpha_asc, alpha_desc",
    ),
    q_facet: Optional[str] = Query(None, description="Search query to filter facet values"),
    adv_q: Optional[str] = Query(
        None,
        description=(
            "JSON array of advanced query clauses. "
            "Each clause: {'op': 'AND|OR|NOT', 'f': 'dct_title_s', 'q': 'Iowa'}"
        ),
    ),
):
    """Get paginated, sortable facet values for a specific facet field within a search resultset.

    This endpoint allows clients to retrieve, sort, paginate, and search through facet values
    for a specific aggregation field. It accepts the same search parameters as /search to
    maintain search context, ensuring facet counts match the current filtered resultset.
    """
    import json

    try:
        # Validate facet name
        try:
            get_facet_aggregation_config(facet_name)
        except ValueError:
            return JSONResponse(
                content={"error": f"Invalid facet name: {facet_name}"}, status_code=400
            )

        # Validate sort parameter
        valid_sorts = {"count_desc", "count_asc", "alpha_asc", "alpha_desc"}
        if sort not in valid_sorts:
            return JSONResponse(
                content={
                    "error": f"Invalid sort parameter. Must be one of: {', '.join(valid_sorts)}"
                },
                status_code=400,
            )

        # Parse adv_q from JSON string if provided
        parsed_adv_q = None
        if adv_q:
            try:
                parsed_adv_q = json.loads(adv_q)
            except json.JSONDecodeError as e:
                return JSONResponse(
                    content={"error": f"Invalid JSON in adv_q parameter: {str(e)}"},
                    status_code=400,
                )

        # Extract filters from query parameters (similar to search endpoint)
        from app.services.search_service import SearchService

        search_service = SearchService()
        request_query_params = str(request.query_params)

        # Extract filter queries
        filter_query = search_service.extract_filter_queries(request_query_params)
        include_filters, exclude_filters = search_service.extract_new_style_filters(
            request_query_params
        )

        # Validate adv_q if provided
        if parsed_adv_q is not None:
            parsed_adv_q = validate_adv_q(parsed_adv_q)

        # Build search criteria for link generation
        search_criteria = get_search_criteria(q, filter_query, 0, 10, None)

        # Get facet values from Elasticsearch
        buckets = await get_facet_values(
            facet_name=facet_name,
            query=q,
            fq=filter_query,
            include_filters=include_filters,
            exclude_filters=exclude_filters,
            adv_q=parsed_adv_q,
            q_facet=q_facet,
        )

        # Process and format facet response
        facet_data = process_facet_response(
            buckets=buckets,
            facet_name=facet_name,
            search_criteria=search_criteria,
            page=page,
            per_page=per_page,
            sort=sort,
            q_facet=q_facet,
        )

        # Create pagination links
        links = create_pagination_links(
            request,
            page,
            facet_data["meta"]["totalPages"],
            pagination_type="page",
            allowed_params=FACET_ALLOWED_PARAMS,
        )
        # Single template link to apply a value from this facet while preserving current context
        links["applyTemplate"] = generate_facet_apply_template(
            facet_name,
            {
                "q": q,
                "include_filters": include_filters,
                "exclude_filters": exclude_filters,
                "fq": filter_query,
                "adv_q": parsed_adv_q,
            },
        )

        # Build JSON:API response
        base = create_jsonapi_response(data=[], request_url=str(request.url))
        response = {
            "jsonapi": base.get("jsonapi", {}),
            "links": links,
            "meta": facet_data["meta"],
            "data": facet_data["data"],
        }

        return JSONResponse(content=sanitize_for_json(response))

    except HTTPException:
        raise
    except ValueError as e:
        return JSONResponse(content={"error": str(e)}, status_code=400)
    except Exception as e:
        logger.error(f"Error getting facet values: {str(e)}", exc_info=True)
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
