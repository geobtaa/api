# ruff: noqa: E501
import asyncio
import base64
import hashlib
import json

import aiohttp
from fastapi import HTTPException, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.sql import select

from app.api.v1.utils import _get_thumbnail_asset_url, sanitize_for_json
from app.services.distribution_repository import fetch_distribution_context
from app.services.image_service import ImageService
from app.services.static_map_service import StaticMapService
from app.services.thumbnail_queue_service import acquire_thumbnail_queue_slot
from app.services.thumbnail_state_service import (
    ThumbnailState,
    ThumbnailStatePayload,
    safe_record_thumbnail_state,
)
from app.tasks.worker import (
    _cog_thumbnail_image_hash,
    _generate_cog_thumbnail_bytes,
    _generate_pmtiles_thumbnail_bytes,
    _pmtiles_thumbnail_image_hash,
    generate_cog_thumbnail,
    generate_pmtiles_thumbnail,
)
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


def _get_first_resource_class(resource_dict: dict) -> str | None:
    """Extract the first resource class from gbl_resourceClass_sm."""
    resource_classes = (
        resource_dict.get("gbl_resourceClass_sm") or resource_dict.get("gbl_resourceclass_sm") or []
    )
    if isinstance(resource_classes, str):
        resource_classes = [resource_classes]
    if resource_classes and resource_classes[0]:
        return str(resource_classes[0]).strip()
    return None


def _canonicalize_resource_class(resource_class: str | None) -> str:
    """Map resource-class variations to the canonical icon set."""
    rc = (resource_class or "").lower().strip()
    if "map" in rc:
        return "maps"
    if "dataset" in rc or "point" in rc or "polygon" in rc or "raster" in rc or "vector" in rc:
        return "datasets"
    if "web service" in rc:
        return "web services"
    if "collection" in rc:
        return "collections"
    if "imager" in rc or "aerial" in rc:
        return "imagery"
    if "website" in rc:
        return "websites"
    if rc in {
        "datasets",
        "maps",
        "web services",
        "collections",
        "imagery",
        "websites",
        "other",
    }:
        return rc
    return "other"


def _resource_class_label(resource_class_key: str) -> str:
    labels = {
        "datasets": "DATASETS",
        "maps": "MAPS",
        "web services": "WEB SERVICES",
        "collections": "COLLECTIONS",
        "imagery": "IMAGERY",
        "websites": "WEBSITES",
        "other": "OTHER",
    }
    return labels.get(resource_class_key, "OTHER")


def _svg_icon_shell(
    *,
    label: str,
    body: str,
    background_data_uri: str | None = None,
    use_gradient: bool = False,
) -> str:
    background = ""
    if background_data_uri:
        background = f"""
  <image href="{background_data_uri}" x="0" y="0" width="200" height="200" preserveAspectRatio="xMidYMid slice"/>
  <rect width="200" height="200" fill="#ffffff" opacity="0.28"/>"""
    elif use_gradient:
        background = """
  <defs>
    <linearGradient id="iconGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#e2e8f0;stop-opacity:1" />
      <stop offset="100%" style="stop-color:#cbd5e1;stop-opacity:1" />
    </linearGradient>
  </defs>
  <rect width="200" height="200" fill="url(#iconGrad)"/>"""
    return f"""<svg width="200" height="200" viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{label} thumbnail fallback">
  <title>{label} thumbnail fallback</title>
  {background}
  {body}
</svg>"""


def _svg_resource_class_icon(
    resource_class: str | None,
    *,
    background_data_uri: str | None = None,
    use_gradient: bool = False,
) -> Response:
    """
    Return an SVG icon for the resource's first resource class.
    Matches the frontend fallback icon set: Datasets, Maps, Web services,
    Collections, Imagery, Websites, and Other.
    """
    rc = _canonicalize_resource_class(resource_class)
    label = _resource_class_label(rc)
    icons = {
        "datasets": """
      <g transform="translate(36 36) scale(0.2)" fill="#173a53">
        <path opacity=".4" d="M96 144L96 192C96 236.2 196.3 272 320 272C443.7 272 544 236.2 544 192L544 144C544 99.8 443.7 64 320 64C196.3 64 96 99.8 96 144zM96 269.8L96 352C96 396.2 196.3 432 320 432C443.7 432 544 396.2 544 352L544 269.8C529.2 279.6 512.2 287.5 494.5 293.8C447.5 310.6 385.8 320 320 320C254.2 320 192.4 310.5 145.5 293.8C127.9 287.5 110.8 279.6 96 269.8zM96 429.8L96 496C96 540.2 196.3 576 320 576C443.7 576 544 540.2 544 496L544 429.8C529.2 439.6 512.2 447.5 494.5 453.8C447.5 470.6 385.8 480 320 480C254.2 480 192.4 470.5 145.5 453.8C127.9 447.5 110.8 439.6 96 429.8z"/>
        <path d="M96 269.8L96 192C96 236.2 196.3 272 320 272C443.7 272 544 236.2 544 192L544 269.8C529.2 279.6 512.2 287.5 494.5 293.8C447.5 310.6 385.8 320 320 320C254.2 320 192.4 310.5 145.5 293.8C127.9 287.5 110.8 279.6 96 269.8zM96 429.8L96 352C96 396.2 196.3 432 320 432C443.7 432 544 396.2 544 352L544 429.8C529.2 439.6 512.2 447.5 494.5 453.8C447.5 470.6 385.8 480 320 480C254.2 480 192.4 470.5 145.5 453.8C127.9 447.5 110.8 439.6 96 429.8z"/>
      </g>""",
        "maps": """
      <g transform="translate(36 36) scale(0.2)" fill="#173a53">
        <path opacity=".4" d="M224 96L416 160L416 544L224 480L224 96z"/>
        <path d="M549.5 477.3L416 544L416 160L541.3 97.4C557.3 89.4 576 101 576 118.9L576 434.4C576 452.6 565.7 469.2 549.5 477.3zM90.5 162.7L224 96L224 480L98.7 542.6C82.8 550.6 64 539 64 521.2L64 205.7C64 187.5 74.3 170.9 90.5 162.8z"/>
      </g>""",
        "web services": """
      <g transform="translate(36 36) scale(0.2)" fill="#173a53">
        <path opacity=".4" d="M96 416L96 480C96 515.3 124.7 544 160 544L480 544C515.3 544 544 515.3 544 480L544 416C544 380.7 515.3 352 480 352L160 352C124.7 352 96 380.7 96 416zM400 448C400 461.3 389.3 472 376 472C362.7 472 352 461.3 352 448C352 434.7 362.7 424 376 424C389.3 424 400 434.7 400 448zM432 192C432 205.3 442.7 216 456 216C469.3 216 480 205.3 480 192C480 178.7 469.3 168 456 168C442.7 168 432 178.7 432 192zM480 448C480 461.3 469.3 472 456 472C442.7 472 432 461.3 432 448C432 434.7 442.7 424 456 424C469.3 424 480 434.7 480 448z"/>
        <path d="M160 96C124.7 96 96 124.7 96 160L96 224C96 259.3 124.7 288 160 288L480 288C515.3 288 544 259.3 544 224L544 160C544 124.7 515.3 96 480 96L160 96zM376 168C389.3 168 400 178.7 400 192C400 205.3 389.3 216 376 216C362.7 216 352 205.3 352 192C352 178.7 362.7 168 376 168zM432 192C432 178.7 442.7 168 456 168C469.3 168 480 178.7 480 192C480 205.3 469.3 216 456 216C442.7 216 432 205.3 432 192zM456 472C469.3 472 480 461.3 480 448C480 434.7 469.3 424 456 424C442.7 424 432 434.7 432 448C432 461.3 442.7 472 456 472z"/>
      </g>""",
        "collections": """
      <g transform="translate(36 36) scale(0.2)" fill="#173a53">
        <path opacity=".4" d="M240 112L240 464L496 464L496 256L352 256L352 112L240 112z"/>
        <path d="M352 112L352 256L496 256L496 464L240 464L240 112L352 112zM400 115.9L492.1 208L400 208L400 115.9zM416 64L192 64L192 512L544 512L544 192L416 64zM144 160L96 160L96 608L448 608L448 560L144 560L144 160z"/>
      </g>""",
        "imagery": """
      <g transform="translate(36 36) scale(0.2)" fill="#173a53">
        <path opacity=".4" d="M96 160L96 480C96 515.3 124.7 544 160 544L480 544C515.3 544 544 515.3 544 480L544 160C544 124.7 515.3 96 480 96L160 96C124.7 96 96 124.7 96 160zM162.7 467.1C158.6 459.2 159.2 449.6 164.3 442.3L220.3 362.3C224.8 355.9 232.1 352.1 240 352.1C247.9 352.1 255.2 355.9 259.7 362.3L286.1 400.1L347.5 299.6C351.9 292.5 359.6 288.1 368 288.1C376.4 288.1 384.1 292.5 388.5 299.6L476.5 443.6C481 451 481.2 460.3 477 467.9C472.8 475.5 464.7 480 456 480L184 480C175.1 480 166.8 475 162.7 467.1zM272 224C272 250.5 250.5 272 224 272C197.5 272 176 250.5 176 224C176 197.5 197.5 176 224 176C250.5 176 272 197.5 272 224z"/>
        <path d="M388.5 299.5C384.1 292.4 376.4 288 368 288C359.6 288 351.9 292.4 347.5 299.5L286.1 400L259.7 362.2C255.2 355.8 247.9 352 240 352C232.1 352 224.8 355.8 220.3 362.2L164.3 442.2C159.2 449.5 158.5 459.1 162.7 467C166.9 474.9 175.1 480 184 480L456 480C464.7 480 472.7 475.3 476.9 467.7C481.1 460.1 481 450.9 476.4 443.4L388.4 299.4z"/>
      </g>""",
        "websites": """
      <g transform="translate(36 36) scale(0.2)" fill="#173a53">
        <path opacity=".4" d="M64 320L576 320L576 448C576 483.3 547.3 512 512 512L128 512C92.7 512 64 483.3 64 448L64 320z"/>
        <path d="M64 192C64 156.7 92.7 128 128 128L512 128C547.3 128 576 156.7 576 192L576 320L64 320L64 192zM192 224C192 206.3 177.7 192 160 192C142.3 192 128 206.3 128 224C128 241.7 142.3 256 160 256C177.7 256 192 241.7 192 224zM248 200C234.7 200 224 210.7 224 224C224 237.3 234.7 248 248 248L488 248C501.3 248 512 237.3 512 224C512 210.7 501.3 200 488 200L248 200z"/>
      </g>""",
        "other": """
      <g transform="translate(36 36) scale(0.2)" fill="#173a53">
        <path opacity=".4" d="M128 128L128 512C128 547.3 156.7 576 192 576L448 576C483.3 576 512 547.3 512 512L512 224L384 224C366.3 224 352 209.7 352 192L352 64L192 64C156.7 64 128 92.7 128 128z"/>
        <path d="M352 64C367.4 64 382.1 70.1 393 81L495 183C505.9 193.9 512 208.6 512 224L384 224C366.3 224 352 209.7 352 192L352 64z"/>
      </g>""",
    }
    body = icons.get(rc) or icons["other"]
    svg = _svg_icon_shell(
        label=label,
        body=body.strip(),
        background_data_uri=background_data_uri,
        use_gradient=use_gradient,
    )
    return Response(
        content=svg,
        media_type="image/svg+xml",
        headers={
            "Cache-Control": "no-store",
            "X-Placeholder": "true",
        },
    )


async def _svg_icon_on_gradient(resource_dict: dict) -> Response:
    """Return a resource-class icon on a gradient background (no map)."""
    return _svg_resource_class_icon(
        _get_first_resource_class(resource_dict),
        use_gradient=True,
    )


async def _svg_icon_for_resource(resource_dict: dict, *, variant: str = "icon-basemap") -> Response:
    """
    Return a resource-class icon, optionally layered over a basemap or gradient.
    variant: 'icon-basemap' (default) = icon on basemap; 'icon-gradient' = icon on gradient.
    """
    if variant == "icon-gradient":
        return await _svg_icon_on_gradient(resource_dict)

    background_data_uri = None
    resource_id = resource_dict.get("id")
    if resource_id:
        try:
            # Match the regular static-map render dimensions so fit/zoom are identical
            # before the square thumbnail crop is applied in the SVG.
            map_service = StaticMapService()
            resource_id = str(resource_id)
            map_bytes = await map_service.get_cached_basemap(resource_id)
            if not map_bytes:
                geometry = resource_dict.get("locn_geometry") or resource_dict.get("dcat_bbox")
                generator = (
                    map_service.generate_basemap
                    if geometry
                    else map_service.generate_global_basemap
                )
                map_bytes = (
                    await asyncio.to_thread(generator, resource_id, geometry)
                    if geometry
                    else await asyncio.to_thread(generator, resource_id)
                )
            if map_bytes:
                encoded = base64.b64encode(map_bytes).decode("ascii")
                background_data_uri = f"data:image/png;base64,{encoded}"
        except Exception as e:
            logger.debug(f"Unable to load basemap background for {resource_id}: {e}")

    return _svg_resource_class_icon(
        _get_first_resource_class(resource_dict),
        background_data_uri=background_data_uri,
    )


def _svg_collection_icon() -> Response:
    """SVG icon for Collection resources (legacy alias)."""
    return _svg_resource_class_icon("Collections")


async def _fetch_resource_dict(id: str) -> dict | None:
    """Load a resource row as a JSON-safe dict for thumbnail asset generation."""
    async with async_session() as session:
        query = select(resources).where(resources.c.id == id)
        result = await session.execute(query)
        row = result.fetchone()

        if not row:
            return None

        return sanitize_for_json(dict(row._mapping))


async def _get_resource_thumbnail_response(
    id: str,
    request: Request,
    *,
    variant: str = "icon-basemap",
    not_found_placeholder: bool = True,
) -> Response:
    """Resolve the resource thumbnail response for a specific fallback variant."""
    resource_dict = await _fetch_resource_dict(id)
    if not resource_dict:
        if not_found_placeholder:
            return _svg_placeholder(title="Thumbnail unavailable", subtitle="Resource not found")
        raise HTTPException(status_code=404, detail="Resource not found")

    # Check for restricted access rights
    if resource_dict.get("dct_accessrights_s") == "Restricted":
        return _svg_placeholder(title="Thumbnail unavailable", subtitle="Restricted resource")

    # Prefer bridge-synced thumbnail assets (e.g., S3-backed thumbnails) when present.
    # These are exposed in meta.ui.thumbnail_url for API clients, but we also want the
    # legacy /resources/{id}/thumbnail endpoint to serve them directly.
    asset_url = await _get_thumbnail_asset_url(id)
    if asset_url:
        asset_ok = await _probe_thumbnail_url(asset_url)
        if asset_ok:
            return RedirectResponse(
                url=asset_url,
                status_code=302,
                headers={
                    # Allow browsers/CDNs to cache the concrete image URL aggressively.
                    "Cache-Control": "public, max-age=31536000, immutable",
                },
            )
        logger.info(
            "Thumbnail asset URL is unreachable or invalid for %s; falling back to generated asset",
            id,
        )

    # Get distribution context and image service
    distribution_context = await fetch_distribution_context(id)
    image_service = ImageService(resource_dict, distribution_context=distribution_context)

    # Determine the source thumbnail URL
    source_url = image_service._get_thumbnail_source_url()

    if not source_url:
        # No thumbnail source: show resource-class icon
        await safe_record_thumbnail_state(
            ThumbnailStatePayload(
                resource_id=id,
                state=ThumbnailState.PLACEHELD,
                source_type=None,
                source_url=None,
                state_detail="No thumbnail source available; using placeholder",
            )
        )
        return await _svg_icon_for_resource(resource_dict, variant=variant)

    # Check if we have a cached image
    image_hash = None

    # For COG URLs, use COG-specific hash and task
    if image_service._is_cog_url(source_url):
        image_hash = _cog_thumbnail_image_hash(source_url)
    # For PMTiles URLs, use PMTiles-specific hash and task
    elif image_service._is_pmtiles_url(source_url):
        image_hash = _pmtiles_thumbnail_image_hash(source_url)
    # For manifest URLs, try to resolve from cache
    elif image_service._is_manifest_url(source_url):
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
            await safe_record_thumbnail_state(
                ThumbnailStatePayload(
                    resource_id=id,
                    state=ThumbnailState.SUCCESS,
                    source_type=(
                        "cog"
                        if image_service._is_cog_url(source_url)
                        else "pmtiles"
                        if image_service._is_pmtiles_url(source_url)
                        else "manifest"
                        if image_service._is_manifest_url(source_url)
                        else "remote"
                    ),
                    source_url=source_url,
                    source_hash=image_hash,
                    state_detail="Thumbnail cache hit",
                )
            )
            # Image exists, redirect to the serving endpoint (same pattern as static-maps)
            return RedirectResponse(
                url=f"/api/v1/thumbnails/{image_hash}",
                status_code=302,
                headers={
                    # Don't let caches pin the redirect response itself.
                    "Cache-Control": "no-store",
                },
            )
        # PMTiles: if we previously failed (e.g. vector tiles), show resource-class icon
        if image_service._is_pmtiles_url(source_url) and image_service.is_pmtiles_skip_cached(
            image_hash
        ):
            logger.info(f"PMTiles thumbnail skipped for {id}, showing resource-class icon")
            await safe_record_thumbnail_state(
                ThumbnailStatePayload(
                    resource_id=id,
                    state=ThumbnailState.PLACEHELD,
                    source_type="pmtiles",
                    source_url=source_url,
                    source_hash=image_hash,
                    state_detail="PMTiles skip marker present; using placeholder",
                )
            )
            return await _svg_icon_for_resource(resource_dict, variant=variant)

    # For direct (non-manifest, non-COG, non-PMTiles) thumbnail URLs: probe once
    # so we don't stick on "Generating thumbnail" when source returns 404 or
    # non-image (e.g. ArcGIS /info/thumbnail, dead b1g_image_ss URLs). If probe
    # fails and resource has geometry, serve static map. (COG/PMTiles URLs are
    # processed server-side; skip probe.)
    geometry = resource_dict.get("locn_geometry") or resource_dict.get("dcat_bbox")
    if (
        not image_service._is_manifest_url(source_url)
        and not image_service._is_cog_url(source_url)
        and not image_service._is_pmtiles_url(source_url)
        and geometry
    ):
        fetch_url = image_service._standardize_iiif_url(source_url)
        probe_ok = await _probe_thumbnail_url(fetch_url)
        if not probe_ok:
            logger.info(
                f"Thumbnail source unreachable or invalid for {id}, showing resource-class icon"
            )
            await safe_record_thumbnail_state(
                ThumbnailStatePayload(
                    resource_id=id,
                    state=ThumbnailState.PLACEHELD,
                    source_type="remote",
                    source_url=source_url,
                    source_hash=image_hash,
                    state_detail="Thumbnail probe failed; using placeholder",
                )
            )
            return await _svg_icon_for_resource(resource_dict, variant=variant)

    # Image doesn't exist, trigger Celery task to fetch and cache it
    try:
        if image_service._is_cog_url(source_url):
            if acquire_thumbnail_queue_slot(id, source_url):
                task = generate_cog_thumbnail.delay(source_url, id)
                await safe_record_thumbnail_state(
                    ThumbnailStatePayload(
                        resource_id=id,
                        state=ThumbnailState.QUEUED,
                        source_type="cog",
                        source_url=source_url,
                        source_hash=image_hash,
                        queue_task_id=task.id,
                        state_detail="Queued COG thumbnail generation",
                    )
                )
            else:
                await safe_record_thumbnail_state(
                    ThumbnailStatePayload(
                        resource_id=id,
                        state=ThumbnailState.QUEUED,
                        source_type="cog",
                        source_url=source_url,
                        source_hash=image_hash,
                        state_detail="COG thumbnail generation already queued",
                    )
                )
        elif image_service._is_pmtiles_url(source_url):
            if acquire_thumbnail_queue_slot(id, source_url):
                task = generate_pmtiles_thumbnail.delay(source_url, id)
                await safe_record_thumbnail_state(
                    ThumbnailStatePayload(
                        resource_id=id,
                        state=ThumbnailState.QUEUED,
                        source_type="pmtiles",
                        source_url=source_url,
                        source_hash=image_hash,
                        queue_task_id=task.id,
                        state_detail="Queued PMTiles thumbnail generation",
                    )
                )
            else:
                await safe_record_thumbnail_state(
                    ThumbnailStatePayload(
                        resource_id=id,
                        state=ThumbnailState.QUEUED,
                        source_type="pmtiles",
                        source_url=source_url,
                        source_hash=image_hash,
                        state_detail="PMTiles thumbnail generation already queued",
                    )
                )
        elif image_service._is_manifest_url(source_url):
            image_service._queue_thumbnail_processing(source_url, id)
        else:
            standardized_url = image_service._standardize_iiif_url(source_url)
            image_service._queue_thumbnail_processing(standardized_url, id)
        logger.info(f"Triggered thumbnail generation for resource {id}")
    except Exception as e:
        logger.error(f"Error triggering thumbnail generation for resource {id}: {e}")
        await safe_record_thumbnail_state(
            ThumbnailStatePayload(
                resource_id=id,
                state=ThumbnailState.FAILURE,
                source_type=(
                    "cog"
                    if image_service._is_cog_url(source_url)
                    else "pmtiles"
                    if image_service._is_pmtiles_url(source_url)
                    else "manifest"
                    if image_service._is_manifest_url(source_url)
                    else "remote"
                ),
                source_url=source_url,
                source_hash=image_hash,
                state_detail="Failed to queue thumbnail generation",
                last_error=str(e),
            )
        )

    # Return a placeholder image while the thumbnail is being generated (never JSON to <img>).
    return _svg_placeholder(title="Generating thumbnail", subtitle="Please try again shortly")


@router.get("/resources/{id}/thumbnail")
async def get_resource_thumbnail(
    id: str,
    request: Request,
    variant: str = "icon-basemap",
):
    """
    Get the thumbnail image for a resource.

    Query params:
        variant: 'icon-basemap' (default) = icon on map basemap; 'icon-gradient' = icon on gradient.
        Only applies when serving the SVG fallback (no COG/PMTiles/etc).

    Follows the same pattern as static-maps:
    - Checks if thumbnail is cached
    - If cached: redirects to /api/v1/thumbnails/{image_hash} (serving endpoint)
    - If not cached: queues background job and returns SVG placeholder

    Returns:
        - Redirect to serving endpoint if thumbnail is ready
        - SVG placeholder if thumbnail is not ready yet (queues background job)
    """
    try:
        return await _get_resource_thumbnail_response(
            id,
            request,
            variant=variant,
            not_found_placeholder=True,
        )
    except Exception as e:
        logger.error(f"Error getting thumbnail for resource {id}: {str(e)}", exc_info=True)
        return _svg_placeholder(title="Thumbnail unavailable", subtitle="Error loading thumbnail")


@router.get("/resources/{id}/thumbnail/no-cache")
async def get_resource_thumbnail_no_cache(
    id: str,
    request: Request,
    variant: str = "icon-basemap",
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
            return await _svg_icon_for_resource(resource_dict, variant=variant)

        # For COG: generate thumbnail synchronously
        if image_service._is_cog_url(source_url):
            image_bytes = await asyncio.to_thread(_generate_cog_thumbnail_bytes, source_url)
            if image_bytes:
                return Response(
                    content=image_bytes,
                    media_type="image/png",
                    headers={"Cache-Control": "no-store"},
                )
            return await _svg_icon_for_resource(resource_dict, variant=variant)

        # For PMTiles: generate thumbnail synchronously (raster tiles only; vector falls back)
        if image_service._is_pmtiles_url(source_url):
            image_bytes = await asyncio.to_thread(_generate_pmtiles_thumbnail_bytes, source_url)
            if image_bytes:
                from app.api.v1.endpoint_modules.thumbnails import _detect_image_type

                content_type = _detect_image_type(image_bytes)
                return Response(
                    content=image_bytes,
                    media_type=content_type or "image/png",
                    headers={"Cache-Control": "no-store"},
                )
            return await _svg_icon_for_resource(resource_dict, variant=variant)

        # Resolve manifests to actual image URLs when needed
        if image_service._is_manifest_url(source_url):
            # This may fetch the manifest once to resolve thumbnail URL
            resolved = image_service.get_iiif_manifest_thumbnail(source_url)
            if not resolved:
                return _svg_placeholder(
                    title="Thumbnail unavailable", subtitle="Error resolving IIIF"
                )
            fetch_url = image_service._standardize_iiif_url(resolved)
        else:
            fetch_url = image_service._standardize_iiif_url(source_url)

        # Download image directly (bypass Redis cache)
        image_bytes = await image_service.download_image(fetch_url)
        if not image_bytes:
            return _svg_placeholder(
                title="Thumbnail unavailable", subtitle="Error downloading image"
            )

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
        return _svg_placeholder(
            title="Thumbnail unavailable", subtitle="Error regenerating thumbnail"
        )
