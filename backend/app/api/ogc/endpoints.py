import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.api.errors import PUBLIC_ERROR_RESPONSES
from app.api.schemas import (
    OGCCollectionResponse,
    OGCCollectionsResponse,
    OGCConformanceResponse,
    OGCFeatureCollectionResponse,
    OGCFeatureResponse,
    OGCLandingPageResponse,
    OGCQueryablesResponse,
    OGCSortablesResponse,
)
from app.api.v1.shared import SortOption
from app.api.v1.utils import sanitize_for_json
from app.services.ogc_projector import OGCResponseProjector
from app.services.search_service import SearchService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["OGC API"])


def get_search_service() -> SearchService:
    return SearchService()


def map_ogc_sort(sortby: Optional[str]) -> Optional[str]:
    if not sortby:
        return None

    # OGC supports comma separated list, we take the first mapped one for simplicity
    first = sortby.split(",")[0].strip()

    if first == "title":
        return SortOption.TITLE_AZ.value
    elif first == "-title":
        return SortOption.TITLE_ZA.value
    elif first in ("modified", "dateAccessioned"):
        return SortOption.YEAR_OLDEST.value
    elif first in ("-modified", "-dateAccessioned"):
        return SortOption.YEAR_NEWEST.value
    elif first == "relevance":
        return SortOption.RELEVANCE.value

    return SortOption.RELEVANCE.value


def parse_bbox_to_fq(bbox: Optional[str]) -> Optional[Dict]:
    if not bbox:
        return None

    try:
        parts = [float(p.strip()) for p in bbox.split(",")]
        if len(parts) == 4:
            minx, miny, maxx, maxy = parts
            return {
                "geo": {
                    "type": "bbox",
                    "top_left": {"lat": str(maxy), "lon": str(minx)},
                    "bottom_right": {"lat": str(miny), "lon": str(maxx)},
                }
            }
    except ValueError:
        pass
    return None


@router.get("/", response_model=OGCLandingPageResponse, responses=PUBLIC_ERROR_RESPONSES)
async def get_landing_page(request: Request) -> Dict[str, Any]:
    url = str(request.url)
    return OGCResponseProjector.build_landing_page(url)


@router.get("/conformance", response_model=OGCConformanceResponse, responses=PUBLIC_ERROR_RESPONSES)
async def get_conformance() -> Dict[str, Any]:
    return OGCResponseProjector.build_conformance()


@router.get("/collections", response_model=OGCCollectionsResponse, responses=PUBLIC_ERROR_RESPONSES)
async def get_collections(request: Request) -> Dict[str, Any]:
    url = str(request.url)
    return OGCResponseProjector.build_collections(url)


@router.get(
    "/collections/btaa-records",
    response_model=OGCCollectionResponse,
    responses=PUBLIC_ERROR_RESPONSES,
)
async def get_collection(request: Request) -> Dict[str, Any]:
    url = str(request.url)
    return OGCResponseProjector.build_collection(url, "btaa-records")


@router.get(
    "/collections/btaa-records/queryables",
    response_model=OGCQueryablesResponse,
    responses=PUBLIC_ERROR_RESPONSES,
)
async def get_queryables(request: Request) -> Dict[str, Any]:
    url = str(request.url)
    return OGCResponseProjector.build_queryables(url)


@router.get(
    "/collections/btaa-records/sortables",
    response_model=OGCSortablesResponse,
    responses=PUBLIC_ERROR_RESPONSES,
)
async def get_sortables(request: Request) -> Dict[str, Any]:
    url = str(request.url)
    return OGCResponseProjector.build_sortables(url)


@router.get(
    "/collections/btaa-records/items",
    response_model=OGCFeatureCollectionResponse,
    responses=PUBLIC_ERROR_RESPONSES,
)
async def get_items(
    request: Request,
    q: Optional[str] = Query(None, description="Keyword search query"),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of items to return"),
    page: int = Query(1, ge=1, description="Page number of results to return"),
    sortby: Optional[str] = Query(None, description="OGC sorting parameter"),
    bbox: Optional[str] = Query(None, description="Bounding box (minx,miny,maxx,maxy)"),
    datetime: Optional[str] = Query(None, description="Temporal filter (not fully implemented)"),
    search_service: SearchService = Depends(get_search_service),  # noqa: B008
) -> Dict[str, Any]:
    url = str(request.url)
    internal_sort = map_ogc_sort(sortby)

    # We pass the bbox implicitly through include_filters dict structure
    include_filters = parse_bbox_to_fq(bbox)

    results = await search_service.search(
        q=q,
        page=page,
        limit=limit,
        sort=internal_sort,
        include_filters=include_filters,
        exclude_filters={},  # Empty dict to avoid parsing query params as BTAA filters
        request_query_params=None,
    )

    if isinstance(results, dict) and "error" in results:
        logger.error("OGC search request failed in search service")
        raise HTTPException(status_code=503, detail="Elasticsearch search failed")

    return sanitize_for_json(
        OGCResponseProjector.build_items_response(url, results, page, limit, "btaa-records")
    )


@router.get(
    "/collections/btaa-records/items/{recordId}",
    response_model=OGCFeatureResponse,
    responses=PUBLIC_ERROR_RESPONSES,
)
async def get_item(
    request: Request,
    recordId: str,
    search_service: SearchService = Depends(get_search_service),  # noqa: B008
) -> Dict[str, Any]:
    url = str(request.url)

    try:
        resource_response = await search_service.get_resource(recordId)
    except HTTPException as e:
        if e.status_code >= 500:
            raise HTTPException(status_code=500, detail="Internal server error") from e
        raise
    except Exception as e:
        logger.error(f"Error fetching resource {recordId} for OGC endpoint", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error") from e

    resource = resource_response.get("data")
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")

    return OGCResponseProjector.build_item(url, resource, "btaa-records")
