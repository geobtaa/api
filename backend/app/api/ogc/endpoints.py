import logging
import math
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse

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


class GeoJSONResponse(JSONResponse):
    media_type = "application/geo+json"


class SchemaJSONResponse(JSONResponse):
    media_type = "application/schema+json"


def get_search_service() -> SearchService:
    return SearchService()


def map_ogc_sort(sortby: Optional[str]) -> Optional[str]:
    """Only advertise sorts the backing index can actually execute."""
    if sortby is None:
        return None
    supported = {
        "title": SortOption.TITLE_AZ.value,
        "+title": SortOption.TITLE_AZ.value,
        "-title": SortOption.TITLE_ZA.value,
        "relevance": SortOption.RELEVANCE.value,
        "-relevance": SortOption.RELEVANCE.value,
    }
    value = supported.get(sortby.strip())
    if value is None:
        raise HTTPException(
            status_code=400,
            detail="Unsupported sortby. Use title, +title, -title, relevance, or -relevance.",
        )
    return value


def parse_bbox_to_fq(bbox: Optional[str]) -> Optional[Dict]:
    """Validate a CRS84 bbox and intersect record extents, not centroids."""
    if bbox is None:
        return None
    try:
        parts = [float(p.strip()) for p in bbox.split(",")]
    except ValueError:
        parts = []
    if len(parts) != 4 or not all(math.isfinite(value) for value in parts):
        raise HTTPException(status_code=400, detail="bbox must contain four finite coordinates.")

    west, south, east, north = parts
    if not (
        -180 <= west <= 180
        and -180 <= east <= 180
        and -90 <= south < north <= 90
        and west != east
        and not (west == 180 and east == -180)
    ):
        raise HTTPException(
            status_code=400,
            detail="bbox must be a nonzero-area CRS84 extent within longitude/latitude bounds.",
        )

    geo = {"field": "dcat_bbox", "relation": "intersects"}
    if west > east and west != 180 and east != -180:
        # Wrapped east avoids the native map filter's reversed-corner heuristic.
        # Its two envelopes are ORed and do not apply the map's overlap threshold.
        geo.update(
            {
                "type": "bbox",
                "top_left": {"lat": north, "lon": west},
                "bottom_right": {"lat": south, "lon": east + 360},
            }
        )
    else:
        if west > east:
            west, east = (-180, east) if west == 180 else (west, 180)
        # Shape filters avoid the map search's minimum-overlap script: OGC bbox
        # includes every intersecting extent, even if it only touches an edge.
        geo.update(
            {
                "type": "shape",
                "shape": {"type": "envelope", "coordinates": [[west, north], [east, south]]},
            }
        )
    return {"geo": geo}


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
    response_class=SchemaJSONResponse,
    responses=PUBLIC_ERROR_RESPONSES,
)
async def get_queryables(request: Request) -> Dict[str, Any]:
    url = str(request.url)
    return OGCResponseProjector.build_queryables(url)


@router.get(
    "/collections/btaa-records/sortables",
    response_model=OGCSortablesResponse,
    response_class=SchemaJSONResponse,
    responses=PUBLIC_ERROR_RESPONSES,
)
async def get_sortables(request: Request) -> Dict[str, Any]:
    url = str(request.url)
    return OGCResponseProjector.build_sortables(url)


@router.get(
    "/collections/btaa-records/items",
    response_model=OGCFeatureCollectionResponse,
    response_class=GeoJSONResponse,
    responses=PUBLIC_ERROR_RESPONSES,
)
async def get_items(
    request: Request,
    q: Optional[str] = Query(None, description="Keyword search query"),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of items to return"),
    page: int = Query(1, ge=1, description="Page number of results to return"),
    sortby: Optional[str] = Query(
        None, description="One of title, +title, -title, relevance, -relevance"
    ),
    bbox: Optional[str] = Query(
        None,
        description="CRS84 extent (west,south,east,north); west > east crosses the antimeridian",
    ),
    datetime: Optional[str] = Query(
        None, description="Unsupported: requests with datetime receive HTTP 400"
    ),
    search_service: SearchService = Depends(get_search_service),  # noqa: B008
) -> Dict[str, Any]:
    url = str(request.url)
    supported_params = {"q", "limit", "page", "sortby", "bbox", "datetime"}
    unsupported = set(request.query_params) - supported_params
    if unsupported:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported query parameter(s): {', '.join(sorted(unsupported))}",
        )
    if any(len(request.query_params.getlist(key)) > 1 for key in request.query_params):
        raise HTTPException(status_code=400, detail="Repeated query parameters are unsupported.")
    if datetime is not None:
        raise HTTPException(status_code=400, detail="datetime filtering is not supported.")
    internal_sort = map_ogc_sort(sortby)

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
    response_class=GeoJSONResponse,
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
