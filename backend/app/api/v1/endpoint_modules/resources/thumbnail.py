import hashlib
import json
from typing import Optional

from fastapi import Query
from fastapi.responses import JSONResponse
from sqlalchemy.sql import select

from app.api.v1.utils import create_response, sanitize_for_json
from app.services.distribution_repository import fetch_distribution_context
from app.services.image_service import ImageService
from db.models import resources

from . import async_session, logger, router


@router.get("/resources/{id}/thumbnail")
async def get_resource_thumbnail(
    id: str,
    callback: Optional[str] = Query(None, description="JSONP callback name"),
    debug: bool = Query(False, description="Include debug details about thumbnail resolution"),
):
    """Get the current thumbnail URL (or placeholder) for a resource."""
    try:
        # Fetch resource to access references and other metadata
        async with async_session() as session:
            query = select(resources).where(resources.c.id == id)
            result = await session.execute(query)
            row = result.fetchone()

            if not row:
                return JSONResponse(content={"error": "Resource not found"}, status_code=404)

            resource_dict = sanitize_for_json(dict(row._mapping))

        # Compute thumbnail URL using ImageService
        distribution_context = await fetch_distribution_context(id)
        image_service = ImageService(resource_dict, distribution_context=distribution_context)
        thumbnail_url = image_service.get_thumbnail_url()

        # Determine if it's a placeholder (only true if URL is actually a placeholder)
        # If thumbnail_url is None, placeholder should be false (frontend uses resource class icon)
        is_placeholder = bool(thumbnail_url and "/thumbnails/placeholder" in str(thumbnail_url))

        response_payload = {
            "id": id,
            # Can be None (use resource class), placeholder URL, or actual thumbnail URL
            "thumbnail_url": thumbnail_url,
            "placeholder": is_placeholder,
        }

        # Optional debug block with rich insight into detection and caching
        if debug:
            # Determine raw source URL without network
            source_url = image_service._get_thumbnail_source_url()
            standardized_source = (
                image_service._standardize_iiif_url(source_url) if source_url else None
            )

            # If manifest, try to resolve from cache only (no blocking HTTP calls)
            resolved_url = None
            if (
                source_url
                and isinstance(source_url, str)
                and image_service._is_manifest_url(source_url)
            ):
                try:
                    # Only check cache - don't fetch manifests synchronously
                    manifest_cache_key = f"manifest:{source_url}"
                    cached_manifest_data = image_service.cache.get(manifest_cache_key)
                    if cached_manifest_data:
                        manifest_json = json.loads(cached_manifest_data)
                        resolved_url = image_service._extract_thumbnail_from_manifest_json(
                            manifest_json, source_url
                        )
                        if resolved_url:
                            resolved_url = image_service._standardize_iiif_url(resolved_url)
                except Exception:
                    resolved_url = None

            # Compute the hash key used for caching based on the queued URL (standardized_source)
            image_hash = (
                hashlib.sha256((standardized_source or "").encode()).hexdigest()
                if standardized_source
                else None
            )
            cache_key = f"image:{image_hash}" if image_hash else None

            cache_exists = None
            try:
                if cache_key:
                    cache_exists = bool(image_service.image_cache.exists(cache_key))
            except Exception:
                cache_exists = None

            response_payload["debug"] = {
                "source_url": source_url,
                "standardized_source": standardized_source,
                "resolved_url": resolved_url,
                "image_hash": image_hash,
                "cache_key": cache_key,
                "cache_exists": cache_exists,
            }

        return create_response(response_payload, callback)
    except Exception as e:
        logger.error(f"Error getting thumbnail for resource {id}: {str(e)}", exc_info=True)
        return JSONResponse(content={"error": str(e)}, status_code=500)

