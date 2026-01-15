import hashlib
import json
from typing import Optional

from fastapi import Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.sql import select

from app.api.v1.utils import sanitize_for_json
from app.services.distribution_repository import fetch_distribution_context
from app.services.image_service import ImageService
from db.models import resources

from . import async_session, logger, router


def _svg_placeholder(*, title: str, subtitle: str) -> Response:
    """Generate an SVG placeholder image (same pattern as static-maps)."""
    svg = f"""
    <svg width="200" height="200" xmlns="http://www.w3.org/2000/svg">
      <rect width="200" height="200" fill="#f8fafc" stroke="#e5e7eb" stroke-width="2"/>
      <text x="100" y="95" font-family="Arial, sans-serif" font-size="14"
            text-anchor="middle" fill="#334155">{title}</text>
      <text x="100" y="115" font-family="Arial, sans-serif" font-size="12"
            text-anchor="middle" fill="#64748b">{subtitle}</text>
    </svg>
    """.strip()
    return Response(
        content=svg,
        media_type="image/svg+xml",
        headers={
            # Never cache placeholders; otherwise CDNs/browsers can pin "processing".
            "Cache-Control": "no-store",
            "X-Placeholder": "true",
        },
    )


@router.get("/resources/{id}/thumbnail")
async def get_resource_thumbnail(
    id: str,
    request: Request,
):
    """
    Get the thumbnail image for a resource.
    
    Follows the same pattern as static-maps:
    - Checks if thumbnail is cached
    - If cached: redirects to /api/v1/thumbnails/{image_hash} (serving endpoint)
    - If not cached: queues background job and returns SVG placeholder
    
    Returns:
        - Redirect to serving endpoint if thumbnail is ready
        - SVG placeholder if thumbnail is not ready yet (queues background job)
    """
    try:
        # Fetch resource to access references and other metadata
        async with async_session() as session:
            query = select(resources).where(resources.c.id == id)
            result = await session.execute(query)
            row = result.fetchone()

            if not row:
                return _svg_placeholder(title="Thumbnail unavailable", subtitle="Resource not found")

            resource_dict = sanitize_for_json(dict(row._mapping))

        # Check for restricted access rights
        if resource_dict.get("dct_accessrights_s") == "Restricted":
            return _svg_placeholder(title="Thumbnail unavailable", subtitle="Restricted resource")

        # Get distribution context and image service
        distribution_context = await fetch_distribution_context(id)
        image_service = ImageService(resource_dict, distribution_context=distribution_context)
        
        # Determine the source thumbnail URL
        source_url = image_service._get_thumbnail_source_url()
        
        if not source_url:
            # No thumbnail source available
            return _svg_placeholder(title="No thumbnail", subtitle="No thumbnail source available")

        # Check if we have a cached image
        image_hash = None
        
        # For manifest URLs, try to resolve from cache
        if image_service._is_manifest_url(source_url):
            manifest_cache_key = f"manifest:{source_url}"
            try:
                cached_manifest_data = image_service.cache.get(manifest_cache_key)
                if cached_manifest_data:
                    manifest_json = json.loads(cached_manifest_data)
                    resolved_url = image_service._extract_thumbnail_from_manifest_json(
                        manifest_json, source_url
                    )
                    if resolved_url:
                        resolved_url = image_service._standardize_iiif_url(resolved_url)
                        image_hash = hashlib.sha256(resolved_url.encode()).hexdigest()
            except Exception as e:
                logger.debug(f"Error checking manifest cache for {id}: {e}")
        else:
            # Direct image URL
            standardized_url = image_service._standardize_iiif_url(source_url)
            image_hash = hashlib.sha256(standardized_url.encode()).hexdigest()

        # Check if image is cached
        if image_hash:
            image_data = await image_service.get_cached_image(image_hash)
            if image_data:
                # Image exists, redirect to the serving endpoint (same pattern as static-maps)
                return RedirectResponse(
                    url=f"/api/v1/thumbnails/{image_hash}",
                    status_code=302,
                    headers={
                        # Don't let caches pin the redirect response itself.
                        "Cache-Control": "no-store",
                    },
                )

        # Image doesn't exist, trigger Celery task to fetch and cache it
        try:
            if image_service._is_manifest_url(source_url):
                image_service._queue_thumbnail_processing(source_url, id)
            else:
                standardized_url = image_service._standardize_iiif_url(source_url)
                image_service._queue_thumbnail_processing(standardized_url, id)
            logger.info(f"Triggered thumbnail generation for resource {id}")
        except Exception as e:
            logger.error(f"Error triggering thumbnail generation for resource {id}: {e}")

        # Return a placeholder image while the thumbnail is being generated (never JSON to <img>).
        return _svg_placeholder(title="Generating thumbnail", subtitle="Please try again shortly")

    except Exception as e:
        logger.error(f"Error getting thumbnail for resource {id}: {str(e)}", exc_info=True)
        return _svg_placeholder(title="Thumbnail unavailable", subtitle="Error loading thumbnail")
