import hashlib
import json

import aiohttp
from fastapi import Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.sql import select

from app.api.v1.utils import sanitize_for_json
from app.services.distribution_repository import fetch_distribution_context
from app.services.image_service import ImageService
from db.models import resources

from . import async_session, logger, router

# Timeout for probing thumbnail source URL (avoid blocking; fail fast if 404/unreachable)
THUMBNAIL_PROBE_TIMEOUT = 5


async def _probe_thumbnail_url(url: str) -> bool:
    """
    Try to fetch the thumbnail URL; return True if we get a valid image response.
    Used to avoid showing "Generating thumbnail" forever when the source is 404 or invalid.
    """
    try:
        headers = {"User-Agent": "BTAA-Geospatial-Data-API/1.0 (https://geo.btaa.org/)"}
        timeout = aiohttp.ClientTimeout(total=THUMBNAIL_PROBE_TIMEOUT)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status != 200:
                    logger.debug(f"Thumbnail probe {url}: status {resp.status}")
                    return False
                content = await resp.read()
                content_type = resp.headers.get("Content-Type", "")
                # Basic image check: PNG/JPEG/GIF magic bytes or content-type
                if content_type.startswith("image/"):
                    return len(content) > 0
                if len(content) >= 8:
                    if content[:8] == b"\x89PNG\r\n\x1a\n":
                        return True
                    if content[:2] == b"\xff\xd8":
                        return True
                    if content[:6] in (b"GIF87a", b"GIF89a"):
                        return True
                return False
    except (aiohttp.ClientError, OSError) as e:
        logger.debug(f"Thumbnail probe failed for {url}: {e}")
        return False


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


def _svg_collection_icon() -> Response:
    """SVG icon for Collection resources with no thumbnail and no geometry."""
    svg = """
    <svg width="200" height="200" xmlns="http://www.w3.org/2000/svg">
      <rect width="200" height="200" fill="#f1f5f9" stroke="#cbd5e1" stroke-width="2"/>
      <g transform="translate(60,50)">
        <path d="M0 20 L0 80 L80 80 L80 20 L40 0 Z" fill="#94a3b8" stroke="#64748b" stroke-width="2"/>
        <path d="M10 30 L70 30 L70 75 L10 75 Z" fill="#cbd5e1" stroke="#64748b" stroke-width="1"/>
        <rect x="25" y="40" width="20" height="12" fill="#94a3b8" rx="1"/>
        <rect x="25" y="56" width="30" height="12" fill="#94a3b8" rx="1"/>
      </g>
    </svg>
    """.strip()
    return Response(
        content=svg,
        media_type="image/svg+xml",
        headers={
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
                return _svg_placeholder(
                    title="Thumbnail unavailable", subtitle="Resource not found"
                )

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
            # No thumbnail source: use static map when resource has geometry
            geometry = resource_dict.get("locn_geometry") or resource_dict.get("dcat_bbox")
            if geometry:
                return RedirectResponse(
                    url=f"/api/v1/resources/{id}/static-map",
                    status_code=302,
                    headers={"Cache-Control": "no-store"},
                )
            # Collection with no thumbnail and no geometry: show collection icon
            resource_classes = resource_dict.get("gbl_resourceClass_sm") or resource_dict.get("gbl_resourceclass_sm") or []
            if isinstance(resource_classes, str):
                resource_classes = [resource_classes]
            if "Collections" in resource_classes:
                return _svg_collection_icon()
            return _svg_placeholder(title="Thumbnail", subtitle="Not available")

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

        # For direct (non-manifest) thumbnail URLs: probe once so we don't stick on
        # "Generating thumbnail" when the source returns 404 or non-image (e.g. ArcGIS
        # /info/thumbnail not supported). If probe fails and resource has geometry,
        # serve static map instead.
        geometry = resource_dict.get("locn_geometry") or resource_dict.get("dcat_bbox")
        if not image_service._is_manifest_url(source_url) and geometry:
            fetch_url = image_service._standardize_iiif_url(source_url)
            probe_ok = await _probe_thumbnail_url(fetch_url)
            if not probe_ok:
                logger.info(
                    f"Thumbnail source unreachable or invalid for {id}, redirecting to static map"
                )
                return RedirectResponse(
                    url=f"/api/v1/resources/{id}/static-map",
                    status_code=302,
                    headers={"Cache-Control": "no-store"},
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


@router.get("/resources/{id}/thumbnail/no-cache")
async def get_resource_thumbnail_no_cache(
    id: str,
    request: Request,
):
    """
    Regenerate and serve a thumbnail for a resource without relying on cached images.
    Useful for testing what thumbnail would be created.
    """
    try:
        # Fetch resource
        async with async_session() as session:
            query = select(resources).where(resources.c.id == id)
            result = await session.execute(query)
            row = result.fetchone()

            if not row:
                return _svg_placeholder(
                    title="Thumbnail unavailable", subtitle="Resource not found"
                )

            resource_dict = sanitize_for_json(dict(row._mapping))

        if resource_dict.get("dct_accessrights_s") == "Restricted":
            return _svg_placeholder(title="Thumbnail unavailable", subtitle="Restricted resource")

        distribution_context = await fetch_distribution_context(id)
        image_service = ImageService(resource_dict, distribution_context=distribution_context)

        source_url = image_service._get_thumbnail_source_url()
        if not source_url:
            geometry = resource_dict.get("locn_geometry") or resource_dict.get("dcat_bbox")
            if geometry:
                # Fall back to static map for resources with geometry
                return RedirectResponse(
                    url=f"/api/v1/resources/{id}/static-map/no-cache",
                    status_code=302,
                    headers={"Cache-Control": "no-store"},
                )
            # Collection with no thumbnail and no geometry: show collection icon instead of text
            resource_classes = resource_dict.get("gbl_resourceClass_sm") or resource_dict.get("gbl_resourceclass_sm") or []
            if isinstance(resource_classes, str):
                resource_classes = [resource_classes]
            if "Collections" in resource_classes:
                return _svg_collection_icon()
            return _svg_placeholder(title="Thumbnail", subtitle="Not available")

        # Resolve manifests to actual image URLs when needed
        if image_service._is_manifest_url(source_url):
            # This may fetch the manifest once to resolve thumbnail URL
            resolved = image_service.get_iiif_manifest_thumbnail(source_url)
            if not resolved:
                return _svg_placeholder(title="Thumbnail unavailable", subtitle="Error resolving IIIF")
            fetch_url = image_service._standardize_iiif_url(resolved)
        else:
            fetch_url = image_service._standardize_iiif_url(source_url)

        # Download image directly (bypass Redis cache)
        image_bytes = await image_service.download_image(fetch_url)
        if not image_bytes:
            return _svg_placeholder(title="Thumbnail unavailable", subtitle="Error downloading image")

        # Detect content type similarly to the cached thumbnail endpoint
        from app.api.v1.endpoint_modules.thumbnails import _detect_image_type

        content_type = _detect_image_type(image_bytes)

        return Response(
            content=image_bytes,
            media_type=content_type,
            headers={"Cache-Control": "no-store"},
        )
    except Exception as e:
        logger.error(f"Error regenerating thumbnail for resource {id}: {str(e)}", exc_info=True)
        return _svg_placeholder(title="Thumbnail unavailable", subtitle="Error regenerating thumbnail")
