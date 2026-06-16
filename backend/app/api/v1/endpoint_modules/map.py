import json
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from app.api.errors import PUBLIC_ERROR_RESPONSES
from app.api.schemas import MapH3Response
from app.api.v1.advanced_search_utils import validate_adv_q
from app.elasticsearch.search import map_h3_aggregation
from app.services.cache_service import cached_endpoint
from app.services.search_service import SearchService

logger = logging.getLogger(__name__)

router = APIRouter()

# Aggressive caching: hex aggregation is expensive and data changes only on reindex
MAP_H3_CACHE_TTL = 7200  # 2 hours


@router.get("/map/h3", response_model=MapH3Response, responses=PUBLIC_ERROR_RESPONSES)
@cached_endpoint(ttl=MAP_H3_CACHE_TTL, tags=["map"])
async def map_h3(
    request: Request,
    q: Optional[str] = Query(None, description="Search query"),
    adv_q: Optional[str] = Query(
        None,
        description=(
            "JSON array of advanced query clauses. "
            "Each clause: {'op': 'AND|OR|NOT', 'f': 'dct_title_s', 'q': 'Iowa'}"
        ),
    ),
    bbox: Optional[str] = Query(
        None,
        description="Viewport bbox as west,south,east,north",
    ),
    resolution: int = Query(5, ge=2, le=8, description="H3 resolution (2–8)"),
    include_non_public: bool = Query(
        False,
        description="Include unpublished and suppressed records in map aggregates",
    ),
):
    """Return H3 hex aggregates and global count for the map hex layer.

    Uses the request query string for include_filters / exclude_filters (same as
    search) so filters stay in sync. bbox and resolution are map-specific.
    """
    parsed_adv_q = None
    if adv_q:
        try:
            parsed_adv_q = validate_adv_q(json.loads(adv_q))
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON in adv_q parameter") from None
        except HTTPException:
            raise

    try:
        raw = (
            request.scope.get("query_string", b"").decode("utf-8")
            if isinstance(request.scope.get("query_string"), bytes)
            else (request.scope.get("query_string") or "")
        )
        query_string = raw or (request.url.query or "")
        search_service = SearchService()
        include_filters, exclude_filters = search_service.extract_new_style_filters(query_string)
        fq = search_service.extract_filter_queries(query_string) or {}

        result = await map_h3_aggregation(
            q=q,
            fq=fq or None,
            include_filters=include_filters or None,
            exclude_filters=exclude_filters or None,
            adv_q=parsed_adv_q,
            bbox=bbox,
            resolution=resolution,
            include_non_public=include_non_public,
        )
        return JSONResponse(content=result)
    except Exception as e:
        logger.exception("map/h3 failed: %s", e)
        # Return 5xx so cached_endpoint does not cache error responses
        raise HTTPException(status_code=500, detail="Failed to build map aggregates") from e
