import asyncio
import json
import logging
import os
import time
from typing import Annotated, Optional

from fastapi import APIRouter, Body, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

from app.api.v1.advanced_search_utils import validate_adv_q
from app.api.v1.strong_params import FACET_ALLOWED_PARAMS
from app.api.v1.utils import (
    _get_thumbnail_asset_urls,
    create_jsonapi_response,
    create_pagination_links,
    process_resource,
    sanitize_for_json,
)
from app.elasticsearch.search import (
    generate_facet_apply_template,
    get_facet_aggregation_config,
    get_facet_values,
    get_search_criteria,
    process_facet_response,
)
from app.services.allmaps_service import fetch_allmaps_attributes_map
from app.services.cache_service import ENDPOINT_CACHE, CacheService, cached_endpoint
from app.services.data_dictionary_repository import (
    fetch_resource_data_dictionaries_map,
    serialize_resource_data_dictionaries,
)
from app.services.distribution_repository import (
    build_distribution_context,
    fetch_distribution_context_map,
)
from app.services.download_service import fetch_bridge_asset_download_rows_map
from app.services.licensed_access_repository import (
    fetch_resource_licensed_accesses_map,
    serialize_resource_licensed_accesses,
)
from app.services.relationship_service import RelationshipService
from app.services.resource_representation_cache import (
    RESOURCE_SEARCH_RESULT_REPRESENTATION_PROFILE,
    get_cached_resource_representations,
    store_resource_representations,
)
from app.services.search_service import SearchService
from app.services.viewer_service import create_viewer_attributes
from db.async_engine import create_app_async_engine
from db.config import DATABASE_URL
from db.models import resources

logger = logging.getLogger(__name__)

router = APIRouter()

# Cache TTL configuration in seconds
SEARCH_CACHE_TTL = int(3600)  # 1 hour
SUGGEST_CACHE_TTL = int(7200)  # 2 hours
SEARCH_RESULT_CACHE_TTL = int(os.getenv("SEARCH_RESULT_CACHE_TTL", str(SEARCH_CACHE_TTL)))
SEARCH_RESULT_CACHE_VERSION = os.getenv("SEARCH_RESULT_CACHE_VERSION", "v1")
SEARCH_RESULT_CACHE_NAMESPACE = "search.results"
SEARCH_RESULT_CACHE_ENABLED = os.getenv("SEARCH_RESULT_CACHE", "true").lower() == "true"
SEARCH_RESULT_CACHE_LOCK_WAIT_SECONDS = float(
    os.getenv("SEARCH_RESULT_CACHE_LOCK_WAIT_SECONDS", "0.25")
)
SEARCH_RESPONSE_TIMING_LOG_THRESHOLD_MS = float(
    os.getenv("SEARCH_RESPONSE_TIMING_LOG_THRESHOLD_MS", "750")
)
SEARCH_TIMING_HEADERS = os.getenv("SEARCH_TIMING_HEADERS", "true").lower() == "true"
SEARCH_RESULT_RELATIONSHIP_LIMIT = int(os.getenv("SEARCH_RESULT_RELATIONSHIP_LIMIT", "5"))

# Create async engine and session for search results processing
engine = create_app_async_engine(DATABASE_URL)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


def _extract_search_hit(item: dict) -> tuple[dict | None, dict | None]:
    """Normalize a search-layer hit into result metadata and raw resource attributes."""
    if not isinstance(item, dict):
        return None, None

    attrs = item.get("attributes")
    if not isinstance(attrs, dict) or not attrs:
        attrs = None

    rid = item.get("id")
    if not rid and attrs:
        rid = attrs.get("id")
    if not rid:
        nested_attrs = attrs.get("attributes", {}) if attrs else {}
        if isinstance(nested_attrs, dict):
            rid = nested_attrs.get("id")
    if not rid:
        return None, None

    score = item.get("score")
    if score is None and attrs:
        score = attrs.get("score")

    overlap = item.get("bbox_overlap_ratio")
    if overlap is None and attrs:
        overlap = attrs.get("bbox_overlap_ratio")

    containment = item.get("bbox_containment_ratio")
    if containment is None and attrs:
        containment = attrs.get("bbox_containment_ratio")

    spatial_score = item.get("bbox_spatial_score")
    if spatial_score is None and attrs:
        spatial_score = attrs.get("bbox_spatial_score")

    return (
        {
            "id": rid,
            "score": score,
            "bbox_overlap_ratio": overlap,
            "bbox_containment_ratio": containment,
            "bbox_spatial_score": spatial_score,
        },
        attrs,
    )


def _serialize_data_dictionaries_by_id(data_dictionaries_by_id: dict) -> dict[str, list[dict]]:
    payloads: dict[str, list[dict]] = {}
    for resource_id, dictionaries in data_dictionaries_by_id.items():
        if not dictionaries:
            continue
        payloads[str(resource_id)] = sanitize_for_json(
            serialize_resource_data_dictionaries(dictionaries)
        )
    return payloads


def _serialize_licensed_accesses_by_id(licensed_accesses_by_id: dict) -> dict[str, list[dict]]:
    payloads: dict[str, list[dict]] = {}
    for resource_id, accesses in licensed_accesses_by_id.items():
        if not accesses:
            continue
        payloads[str(resource_id)] = sanitize_for_json(
            serialize_resource_licensed_accesses(accesses)
        )
    return payloads


def _log_search_response_timing(**payload: float | int | str) -> None:
    total_ms = float(payload.get("totalMs") or 0)
    cache_status = str(payload.get("semanticCacheStatus") or "")
    should_info = total_ms >= SEARCH_RESPONSE_TIMING_LOG_THRESHOLD_MS or cache_status in {
        "miss",
        "wait_miss",
    }
    if should_info:
        logger.info("search_response_timing %s", json.dumps(payload, sort_keys=True))
    elif logger.isEnabledFor(logging.DEBUG):
        logger.debug("search_response_timing %s", json.dumps(payload, sort_keys=True))


def _canonical_filter_value(value):
    if isinstance(value, dict):
        return {str(k): _canonical_filter_value(value[k]) for k in sorted(value.keys())}
    if isinstance(value, list):
        normalized = [_canonical_filter_value(item) for item in value]
        return sorted(
            normalized,
            key=lambda item: json.dumps(item, sort_keys=True, default=str),
        )
    return value


def _build_semantic_search_cache_key(
    *,
    q,
    page: int,
    per_page: int,
    sort,
    search_field,
    fields,
    facets,
    include_filters,
    exclude_filters,
    fq,
    adv_q,
) -> str:
    """Cache key for the expensive request-independent search response core."""
    return CacheService.generate_cache_key(
        SEARCH_RESULT_CACHE_NAMESPACE,
        version=SEARCH_RESULT_CACHE_VERSION,
        index=os.getenv("ELASTICSEARCH_INDEX", "btaa_geospatial_api"),
        q=q or "",
        page=page,
        per_page=per_page,
        sort=sort or "",
        search_field=search_field or "",
        fields=fields or "",
        facets=facets or "",
        include_filters=_canonical_filter_value(include_filters or {}),
        exclude_filters=_canonical_filter_value(exclude_filters or {}),
        fq=_canonical_filter_value(fq or {}),
        adv_q=adv_q or [],
    )


def _resource_tags_from_response_core(response_core: dict) -> set[str]:
    """Return resource tags for the cached search core payload."""
    data = response_core.get("data")
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        return set()

    tags: set[str] = set()
    for item in data:
        if not isinstance(item, dict):
            continue
        resource_id = item.get("id")
        if not resource_id:
            attributes = item.get("attributes")
            if isinstance(attributes, dict):
                resource_id = attributes.get("id")
        if resource_id:
            tags.add(f"resource:{resource_id}")
    return tags


async def _get_cached_search_response_core(
    *,
    cache_service: CacheService,
    cache_key: str,
    timings: dict[str, float | int | str],
) -> tuple[dict | None, str]:
    if not SEARCH_RESULT_CACHE_ENABLED or not ENDPOINT_CACHE:
        timings["semanticCacheLookupMs"] = 0
        return None, "disabled"

    if getattr(cache_service, "_redis_client", True) is None:
        timings["semanticCacheLookupMs"] = 0
        return None, "disabled"

    lookup_started_at = time.perf_counter()
    cached_core = await cache_service.get(cache_key)
    timings["semanticCacheLookupMs"] = round((time.perf_counter() - lookup_started_at) * 1000, 2)
    if isinstance(cached_core, dict):
        return cached_core, "hit"

    lock_key = f"{cache_key}:lock"
    if await cache_service.acquire_lock(lock_key):
        return None, "miss"

    wait_started_at = time.perf_counter()
    deadline = wait_started_at + SEARCH_RESULT_CACHE_LOCK_WAIT_SECONDS
    while time.perf_counter() < deadline:
        await asyncio.sleep(0.05)
        cached_core = await cache_service.get(cache_key)
        if isinstance(cached_core, dict):
            timings["semanticCacheWaitMs"] = round(
                (time.perf_counter() - wait_started_at) * 1000, 2
            )
            return cached_core, "wait_hit"

    timings["semanticCacheWaitMs"] = round((time.perf_counter() - wait_started_at) * 1000, 2)
    return None, "wait_miss"


async def _store_cached_search_response_core(
    *,
    cache_service: CacheService,
    cache_key: str,
    response_core: dict,
    timings: dict[str, float | int | str],
) -> None:
    store_started_at = time.perf_counter()
    stored = await cache_service.set(cache_key, response_core, ttl=SEARCH_RESULT_CACHE_TTL)
    timings["semanticCacheStoreMs"] = round((time.perf_counter() - store_started_at) * 1000, 2)
    if stored:
        await cache_service.tag_cache_key(
            cache_key,
            {
                "search",
                SEARCH_RESULT_CACHE_NAMESPACE,
                *_resource_tags_from_response_core(response_core),
            },
            ttl_seconds=SEARCH_RESULT_CACHE_TTL,
        )


def _data_for_resource_meta_preference(data: list, *, include_resource_meta: bool) -> list:
    if include_resource_meta:
        return data
    return [
        {key: value for key, value in item.items() if key != "meta"}
        if isinstance(item, dict)
        else item
        for item in data
    ]


def _server_timing_header(timings: dict[str, float | int | str]) -> str:
    metric_map = {
        "semanticCacheLookupMs": "semantic_cache_lookup",
        "semanticCacheWaitMs": "semantic_cache_wait",
        "semanticCacheStoreMs": "semantic_cache_store",
        "searchMs": "search",
        "resourceCacheLookupMs": "resource_cache_lookup",
        "dbFallbackMs": "db_fallback",
        "missPrefetchMs": "miss_prefetch",
        "missBuildMs": "miss_build",
        "responseBuildMs": "response_build",
        "totalMs": "total",
    }
    parts = []
    for key, name in metric_map.items():
        value = timings.get(key)
        if isinstance(value, (int, float)):
            parts.append(f"{name};dur={float(value):.2f}")
    status = timings.get("semanticCacheStatus")
    if status:
        parts.append(f'semantic_cache;desc="{status}"')
    return ", ".join(parts)


def _build_search_json_response(
    *,
    request: Request,
    response_core: dict,
    page: int,
    total_pages: int,
    include_resource_meta: bool,
    timings: dict[str, float | int | str],
) -> JSONResponse:
    from app.api.v1.strong_params import SEARCH_ALLOWED_PARAMS

    response_build_started_at = time.perf_counter()
    links = create_pagination_links(
        request,
        page,
        total_pages,
        pagination_type="page",
        allowed_params=SEARCH_ALLOWED_PARAMS,
    )
    base = create_jsonapi_response(data=[], request_url=str(request.url))
    response = {
        "jsonapi": base.get("jsonapi", {}),
        "links": links,
        "meta": response_core.get("meta", {}),
        "data": _data_for_resource_meta_preference(
            response_core.get("data", []),
            include_resource_meta=include_resource_meta,
        ),
    }
    if "included" in response_core:
        response["included"] = response_core["included"]

    timings["responseBuildMs"] = round((time.perf_counter() - response_build_started_at) * 1000, 2)
    return JSONResponse(content=sanitize_for_json(response))


def _attach_search_timing_headers(
    json_response: JSONResponse,
    timings: dict[str, float | int | str],
) -> JSONResponse:
    if SEARCH_TIMING_HEADERS:
        json_response.headers["Server-Timing"] = _server_timing_header(timings)
        if timings.get("semanticCacheStatus"):
            json_response.headers["X-Search-Semantic-Cache"] = str(
                timings["semanticCacheStatus"]
            ).upper()
    return json_response


async def _handle_search(request: Request, params: dict) -> JSONResponse:
    """Shared search executor and response builder for GET and POST.

    Expects params to contain: q, page, per_page, sort, search_field, fields,
    facets, meta, callback, request_query_params (for GET only), include_filters,
    exclude_filters, fq, adv_q.
    """

    request_started_at = time.perf_counter()

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

    timings: dict[str, float | int | str] = {
        "operation": "_handle_search",
        "semanticCacheStatus": "unknown",
    }

    semantic_cache_key = _build_semantic_search_cache_key(
        q=q,
        page=page,
        per_page=per_page,
        sort=sort,
        search_field=search_field,
        fields=fields,
        facets=facets,
        include_filters=include_filters,
        exclude_filters=exclude_filters,
        fq=fq,
        adv_q=adv_q,
    )
    cache_service = CacheService()
    cached_core, semantic_cache_status = await _get_cached_search_response_core(
        cache_service=cache_service,
        cache_key=semantic_cache_key,
        timings=timings,
    )
    timings["semanticCacheStatus"] = semantic_cache_status
    if cached_core is not None:
        cached_meta = cached_core.get("meta", {}) if isinstance(cached_core, dict) else {}
        response = _build_search_json_response(
            request=request,
            response_core=cached_core,
            page=page,
            total_pages=int(cached_meta.get("totalPages", 0) or 0),
            include_resource_meta=bool(meta),
            timings=timings,
        )
        timings["totalMs"] = round((time.perf_counter() - request_started_at) * 1000, 2)
        _log_search_response_timing(**timings)
        return _attach_search_timing_headers(response, timings)

    search_duration_ms = 0.0
    cache_lookup_ms = 0.0
    db_fallback_ms = 0.0
    miss_prefetch_ms = 0.0
    miss_build_ms = 0.0

    # Step 1: Call SearchService
    search_service = SearchService()
    search_started_at = time.perf_counter()
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
        hydrate_hits=False,
        sanitize_response=False,
    )
    search_duration_ms = (time.perf_counter() - search_started_at) * 1000
    if isinstance(results, dict) and "error" in results:
        logger.error("Search service returned an internal error", exc_info=False)
        return JSONResponse(content={"error": "Elasticsearch search failed"}, status_code=500)

    # Step 2: Extract resource IDs and scores
    result_obj = results if isinstance(results, dict) else {}
    resource_data = []
    search_resource_lookup = {}
    for item in result_obj.get("data", []):
        result_data, source_resource = _extract_search_hit(item)
        if result_data is None:
            continue
        resource_data.append(result_data)
        if source_resource is not None:
            search_resource_lookup[result_data["id"]] = source_resource

    resource_ids = [r["id"] for r in resource_data]
    cached_resources = {}
    if resource_ids:
        cache_lookup_started_at = time.perf_counter()
        cached_resources = await get_cached_resource_representations(
            resource_ids,
            profile=RESOURCE_SEARCH_RESULT_REPRESENTATION_PROFILE,
        )
        cache_lookup_ms = (time.perf_counter() - cache_lookup_started_at) * 1000

    missing_resource_ids = [
        resource_id for resource_id in resource_ids if resource_id not in cached_resources
    ]

    # Step 3: Use search-layer resource rows for cache misses first, then fall back to DB only
    # when the search response did not include source attributes.
    source_resources_by_id = dict(search_resource_lookup)
    missing_source_ids = [
        resource_id
        for resource_id in missing_resource_ids
        if resource_id not in source_resources_by_id
    ]
    if missing_source_ids:
        db_fallback_started_at = time.perf_counter()
        try:
            async with async_session() as session:
                query = select(resources).where(resources.c.id.in_(missing_source_ids))
                result = await session.execute(query)
                rows = result.fetchall()
                source_resources_by_id.update(
                    {
                        dict(row._mapping)["id"]: sanitize_for_json(dict(row._mapping))
                        for row in rows
                    }
                )
        except Exception as e:
            # If database query fails (e.g., connection pool closed), log and continue
            # with empty lookup. This allows the endpoint to return empty results rather
            # than crashing.
            logger.warning(f"Database query failed in search endpoint: {str(e)}")
            source_resources_by_id = dict(search_resource_lookup)
        finally:
            db_fallback_ms = (time.perf_counter() - db_fallback_started_at) * 1000

    # Process resources (initialize outside the if block to avoid UnboundLocalError)
    processed_resources = []
    built_resources = {}

    if resource_data:
        if missing_resource_ids:
            async with async_session() as processing_session:
                miss_prefetch_started_at = time.perf_counter()
                distribution_context_lookup = await fetch_distribution_context_map(
                    missing_resource_ids,
                    session=processing_session,
                )
                distribution_contexts = {
                    resource_id: distribution_context_lookup.get(resource_id)
                    or build_distribution_context(resource_id, [])
                    for resource_id in missing_resource_ids
                }
                allmaps_attributes_by_id = await fetch_allmaps_attributes_map(
                    missing_resource_ids,
                    processing_session,
                )
                data_dictionaries_by_id = await fetch_resource_data_dictionaries_map(
                    missing_resource_ids,
                    session=processing_session,
                )
                data_dictionary_payloads_by_id = _serialize_data_dictionaries_by_id(
                    data_dictionaries_by_id
                )
                licensed_accesses_by_id = await fetch_resource_licensed_accesses_map(
                    missing_resource_ids,
                    session=processing_session,
                )
                licensed_access_payloads_by_id = _serialize_licensed_accesses_by_id(
                    licensed_accesses_by_id
                )
                relationship_summaries_by_id = (
                    await RelationshipService.get_resource_relationship_summaries_map(
                        missing_resource_ids,
                        limit_per_predicate=SEARCH_RESULT_RELATIONSHIP_LIMIT,
                    )
                )
                bridge_asset_download_rows_by_id = await fetch_bridge_asset_download_rows_map(
                    missing_resource_ids
                )
                thumbnail_asset_urls_by_id = await _get_thumbnail_asset_urls(missing_resource_ids)
                miss_prefetch_ms = (time.perf_counter() - miss_prefetch_started_at) * 1000

                miss_build_started_at = time.perf_counter()
                for resource_id in missing_resource_ids:
                    source_resource = source_resources_by_id.get(resource_id)
                    if not source_resource:
                        continue
                    relationship_summary = relationship_summaries_by_id.get(resource_id, {})
                    built_resources[resource_id] = await process_resource(
                        source_resource,
                        processing_session,
                        include_similar_items=False,
                        distribution_context=distribution_contexts.get(resource_id),
                        bridge_asset_download_rows=bridge_asset_download_rows_by_id.get(
                            resource_id
                        ),
                        ui_relationships=relationship_summary.get("relationships", {}),
                        ui_relationship_counts=relationship_summary.get("counts"),
                        ui_relationship_browse_links=relationship_summary.get("browse_links"),
                        allmaps_attributes=allmaps_attributes_by_id.get(resource_id),
                        data_dictionaries_payload=data_dictionary_payloads_by_id.get(resource_id),
                        licensed_accesses_payload=licensed_access_payloads_by_id.get(resource_id),
                        thumbnail_asset_url=thumbnail_asset_urls_by_id.get(resource_id),
                    )
                miss_build_ms = (time.perf_counter() - miss_build_started_at) * 1000
            if built_resources:
                await store_resource_representations(
                    built_resources,
                    profile=RESOURCE_SEARCH_RESULT_REPRESENTATION_PROFILE,
                )

        resources_by_id = {**cached_resources, **built_resources}

        for rd in resource_data:
            obj = resources_by_id.get(rd["id"])
            if obj is None:
                continue

            source_resource = source_resources_by_id.get(rd["id"]) or {}

            # Ensure meta.ui.viewer.geometry is present when resource has geometry.
            # Search results must include it for map hover; ViewerService can miss it
            # when keys/format differ from resource detail path.
            if source_resource and (
                source_resource.get("locn_geometry") or source_resource.get("dcat_bbox")
            ):
                ui = (obj.get("meta") or {}).get("ui") or {}
                viewer_geom = (ui.get("viewer") or {}).get("geometry")
                if not viewer_geom:
                    viewer_attrs = create_viewer_attributes(source_resource)
                    geom = viewer_attrs.get("ui_viewer_geometry")
                    if geom:
                        obj.setdefault("meta", {})
                        obj["meta"].setdefault("ui", {})
                        obj["meta"]["ui"].setdefault("viewer", {})
                        obj["meta"]["ui"]["viewer"]["geometry"] = geom

            # obj["attributes"] is already nested with "ogm" and "b1g" structure
            # from create_jsonapi_resource
            attrs = obj.get("attributes", {})

            # Attach ES scoring and bbox spatial metrics into per-resource meta for debugging
            if rd.get("score") is not None:
                obj.setdefault("meta", {})
                obj["meta"]["score"] = rd["score"]
            if rd.get("bbox_overlap_ratio") is not None:
                obj.setdefault("meta", {})
                obj["meta"]["bbox_overlap_ratio"] = rd["bbox_overlap_ratio"]
            if rd.get("bbox_containment_ratio") is not None:
                obj.setdefault("meta", {})
                obj["meta"]["bbox_containment_ratio"] = rd["bbox_containment_ratio"]
            if rd.get("bbox_spatial_score") is not None:
                obj.setdefault("meta", {})
                obj["meta"]["bbox_spatial_score"] = rd["bbox_spatial_score"]

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

            processed_resources.append(obj)

    # Step 4: Build the request-independent response core.
    pages_info = result_obj.get("meta", {}).get("pages", {})
    total_count = pages_info.get("total_count", 0)
    total_pages = pages_info.get("total_pages", 0)

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

    response_core = {
        "meta": meta_block,
        "data": processed_resources,
    }
    if isinstance(result_obj, dict) and "included" in result_obj:
        response_core["included"] = result_obj["included"]

    timings.update(
        {
            "builtCount": len(built_resources),
            "resourceCacheLookupMs": round(cache_lookup_ms, 2),
            "cachedCount": len(cached_resources),
            "dbFallbackCount": len(missing_source_ids),
            "dbFallbackMs": round(db_fallback_ms, 2),
            "missBuildMs": round(miss_build_ms, 2),
            "missCount": len(missing_resource_ids),
            "missPrefetchMs": round(miss_prefetch_ms, 2),
            "resourceCount": len(resource_ids),
            "searchMs": round(search_duration_ms, 2),
        }
    )

    if semantic_cache_status != "disabled":
        await _store_cached_search_response_core(
            cache_service=cache_service,
            cache_key=semantic_cache_key,
            response_core=response_core,
            timings=timings,
        )

    response = _build_search_json_response(
        request=request,
        response_core=response_core,
        page=page,
        total_pages=int(total_pages),
        include_resource_meta=bool(meta),
        timings=timings,
    )
    timings["totalMs"] = round((time.perf_counter() - request_started_at) * 1000, 2)
    _log_search_response_timing(**timings)
    return _attach_search_timing_headers(response, timings)


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
        logger.debug(
            "Starting search request: q=%r, page=%s, per_page=%s, sort=%r",
            q,
            page,
            per_page,
            sort,
        )

        # Parse adv_q from JSON string if provided
        parsed_adv_q = None
        if adv_q:
            try:
                parsed_adv_q = json.loads(adv_q)
            except json.JSONDecodeError:
                return JSONResponse(
                    content={"error": "Invalid JSON in adv_q parameter"},
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
        logger.debug(
            "Search GET: raw_query_string length=%s, query_string length=%s, sample=%s",
            len(raw_query_string),
            len(query_string),
            query_string[:300],
        )

        # Extract filters manually to ensure they are passed correctly
        from app.services.search_service import SearchService

        search_service = SearchService()
        filter_query = search_service.extract_filter_queries(query_string)
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
                "fq": filter_query,
                "include_filters": include_filters,
                "exclude_filters": exclude_filters,
            },
        )
    except HTTPException:
        raise
    except Exception:
        total_duration = time.time() - start_time
        logger.error(
            "Search request failed after %.3fs",
            total_duration,
            exc_info=True,
        )
        return JSONResponse(content={"error": "Search request failed"}, status_code=500)


@router.post("/search")
@cached_endpoint(ttl=SEARCH_CACHE_TTL)
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
    except Exception:
        logger.error("Search POST request failed", exc_info=True)
        return JSONResponse(content={"error": "Search request failed"}, status_code=500)


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
            except json.JSONDecodeError:
                return JSONResponse(
                    content={"error": "Invalid JSON in adv_q parameter"},
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
    except ValueError:
        return JSONResponse(content={"error": "Invalid facet request"}, status_code=400)
    except Exception:
        logger.error("Error getting facet values", exc_info=True)
        return JSONResponse(content={"error": "Failed to get facet values"}, status_code=500)


@router.get("/suggest")
@cached_endpoint(ttl=SUGGEST_CACHE_TTL)
async def suggest(
    request: Request,
    q: str = Query(..., description="Search query for suggestions"),
    callback: Optional[str] = Query(None, description="JSONP callback name"),
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
    except HTTPException:
        raise
    except Exception:
        logger.error("Error getting suggestions", exc_info=True)
        return JSONResponse(content={"error": "Failed to get suggestions"}, status_code=500)
