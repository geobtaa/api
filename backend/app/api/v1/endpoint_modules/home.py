import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request

from app.api.errors import PUBLIC_ERROR_RESPONSES
from app.api.schemas import HomeBlogPostsResponse
from app.api.v1.utils import create_response
from app.services.cache_service import cached_endpoint
from app.services.gin_blog_service import GINBlogService

router = APIRouter()
gin_blog_service = GINBlogService()
logger = logging.getLogger(__name__)

HOME_BLOG_CACHE_TTL = 3600  # 1 hour


@router.get(
    "/home/blog-posts",
    response_model=HomeBlogPostsResponse,
    responses=PUBLIC_ERROR_RESPONSES,
)
@cached_endpoint(ttl=HOME_BLOG_CACHE_TTL, tags=["home", "home_blog"])
async def list_home_blog_posts(
    request: Request,
    limit: int = Query(6, ge=1, le=24),
    theme: Optional[str] = Query(None, description="Theme id from frontend theme registry"),
    tag: Optional[str] = Query(
        None, description="Optional tag filter (exact match, case-insensitive)"
    ),
):
    # Homepage requests should stay fast and deterministic.
    # Blog content is served from the synced local table only; remote sync happens elsewhere.
    resolved_pins: list[str] = []
    try:
        payload = await gin_blog_service.list_home_posts(
            limit=limit,
            pinned_slugs=resolved_pins,
            tag=tag,
        )
    except Exception as exc:
        logger.exception("Failed to load homepage blog posts")
        # Let the cache retain a previous successful response on refresh failure.
        # A cold-cache failure must not become a cached claim that no stories exist.
        raise HTTPException(
            status_code=503,
            detail="Unable to load GIN stories right now.",
            headers={"Cache-Control": "no-store"},
        ) from exc
    return create_response(payload)
