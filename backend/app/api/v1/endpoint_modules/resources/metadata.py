import json
from typing import Optional

import aiohttp
from fastapi import HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.sql import select

from app.api.v1.utils import filter_empty_values, sanitize_for_json
from app.services.distribution_repository import (
    DistributionContext,
    fetch_distribution_context,
)
from app.services.link_service import LinkService
from app.services.metadata_transform_service import (
    MetadataTransformError,
    transform_fgdc_to_html,
    transform_iso_to_html,
)
from app.services.ogm_field_mapper import OGMFieldMapper
from db.models import resources

from . import filter_resource_fields, get_async_session, logger, router

# Format -> list of distribution URIs to try (SSRF-safe: only use resolved resource URLs)
_FORMAT_URIS = {
    "iso": [
        "http://www.isotc211.org/schemas/2005/gmd/",
        "http://www.isotc211.org/schemas/2005/gmd",
    ],
    "fgdc": [
        "http://www.fgdc.gov/schemas/metadata/",
        "http://www.opengis.net/cat/csw/csdgm",
    ],
    "html": ["http://www.w3.org/1999/xhtml"],
}
METADATA_FETCH_TIMEOUT = 30


def _separate_ogm_and_b1g_fields(resource_dict: dict) -> tuple[dict, dict]:
    """
    Separate resource fields into OGM Aardvark fields and B1G custom fields.

    Returns:
        Tuple of (ogm_fields, b1g_fields) dictionaries
    """
    # Map database column names to official Aardvark field names
    aardvark_attributes = OGMFieldMapper.map_resource_fields(resource_dict)

    # Filter out null values and empty arrays from aardvark fields
    ogm_fields = {}
    for key, value in aardvark_attributes.items():
        if value is not None and value != "":
            # Handle empty arrays
            if isinstance(value, list) and len(value) == 0:
                continue
            # Handle arrays with only None/empty values
            if isinstance(value, list) and all(item is None or item == "" for item in value):
                continue
            ogm_fields[key] = value

    # Get OGM Aardvark field set to identify B1G fields
    ogm_aardvark_field_set = OGMFieldMapper.get_ogm_aardvark_fields()

    # B1G fields are all fields that are NOT in the OGM Aardvark field set
    # and are not UI fields
    ui_field_names = [
        "ui_thumbnail_url",
        "ui_citation",
        "ui_citations",
        "ui_downloads",
        "ui_links",
        "ui_viewer_protocol",
        "ui_viewer_endpoint",
        "ui_viewer_geometry",
        "ui_relationships",
        "ui_summaries",
        "ai_summaries",
        "suggest",
    ]

    b1g_fields = {}
    for key, value in resource_dict.items():
        # Skip UI fields, OGM fields, and null/empty values
        if key in ui_field_names:
            continue
        if key in ogm_aardvark_field_set:
            continue
        if value is not None and value != "":
            # Handle empty arrays
            if isinstance(value, list) and len(value) == 0:
                continue
            # Handle arrays with only None/empty values
            if isinstance(value, list) and all(item is None or item == "" for item in value):
                continue
            b1g_fields[key] = value

    # Filter empty values from both dictionaries
    ogm_fields = filter_empty_values(ogm_fields)
    b1g_fields = filter_empty_values(b1g_fields)

    return ogm_fields, b1g_fields


@router.get("/resources/{id}/metadata")
async def get_resource_metadata(
    id: str,
    fields: Optional[str] = Query(None, description="Comma-separated list of fields to return"),
    callback: Optional[str] = Query(None, description="JSONP callback name"),
):
    """Get both OGM and B1G metadata blocks for a resource by ID."""
    try:
        async with get_async_session() as session:
            query = select(resources).where(resources.c.id == id)
            result = await session.execute(query)
            row = result.fetchone()
            if not row:
                return JSONResponse(content={"error": "Resource not found"}, status_code=404)

            # Convert to dict and sanitize datetime objects
            resource_dict = sanitize_for_json(dict(row._mapping))

            # Separate into OGM and B1G fields
            ogm_fields, b1g_fields = _separate_ogm_and_b1g_fields(resource_dict)

            # Rebuild dct_references_s from resource_distributions for OGM output
            try:
                distribution_context = await fetch_distribution_context(id)
                legacy_refs = distribution_context.legacy_reference_payload
                if legacy_refs:
                    ogm_fields["dct_references_s"] = json.dumps(legacy_refs)
            except Exception:
                pass

            # Apply field filtering if fields parameter is provided
            if fields:
                ogm_fields = filter_resource_fields(ogm_fields, fields)
                b1g_fields = filter_resource_fields(b1g_fields, fields)
                logger.info(f"Filtered metadata: ogm={ogm_fields}, b1g={b1g_fields}")

            # Return both blocks without JSON:API wrapping
            response_payload = {}
            if ogm_fields:
                response_payload["ogm"] = ogm_fields
            if b1g_fields:
                response_payload["b1g"] = b1g_fields

            return JSONResponse(content=response_payload)
    except HTTPException:
        # Re-raise HTTP exceptions to maintain their status code
        raise
    except Exception:
        logger.error("Error getting metadata for resource %s", id, exc_info=True)
        return JSONResponse(content={"error": "Failed to get metadata"}, status_code=500)


@router.get("/resources/{id}/metadata/ogm")
async def get_resource_metadata_ogm(
    id: str,
    fields: Optional[str] = Query(None, description="Comma-separated list of fields to return"),
    callback: Optional[str] = Query(None, description="JSONP callback name"),
):
    """Get only the OGM (OpenGeoMetadata Aardvark) metadata block for a resource by ID."""
    try:
        async with get_async_session() as session:
            query = select(resources).where(resources.c.id == id)
            result = await session.execute(query)
            row = result.fetchone()
            if not row:
                return JSONResponse(content={"error": "Resource not found"}, status_code=404)

            # Convert to dict and sanitize datetime objects
            resource_dict = sanitize_for_json(dict(row._mapping))

            # Separate into OGM and B1G fields
            ogm_fields, _ = _separate_ogm_and_b1g_fields(resource_dict)

            # Rebuild dct_references_s from resource_distributions for OGM output
            try:
                distribution_context = await fetch_distribution_context(id)
                legacy_refs = distribution_context.legacy_reference_payload
                if legacy_refs:
                    ogm_fields["dct_references_s"] = json.dumps(legacy_refs)
            except Exception:
                pass

            # Apply field filtering if fields parameter is provided
            if fields:
                ogm_fields = filter_resource_fields(ogm_fields, fields)
                logger.info(f"Filtered OGM metadata: {ogm_fields}")

            # Return only OGM block without JSON:API wrapping
            return JSONResponse(content=ogm_fields)
    except HTTPException:
        # Re-raise HTTP exceptions to maintain their status code
        raise
    except Exception:
        logger.error("Error getting OGM metadata for resource %s", id, exc_info=True)
        return JSONResponse(content={"error": "Failed to get OGM metadata"}, status_code=500)


@router.get("/resources/{id}/metadata/b1g")
async def get_resource_metadata_b1g(
    id: str,
    fields: Optional[str] = Query(None, description="Comma-separated list of fields to return"),
    callback: Optional[str] = Query(None, description="JSONP callback name"),
):
    """Get only the B1G custom metadata block for a resource by ID."""
    try:
        async with get_async_session() as session:
            query = select(resources).where(resources.c.id == id)
            result = await session.execute(query)
            row = result.fetchone()
            if not row:
                return JSONResponse(content={"error": "Resource not found"}, status_code=404)

            # Convert to dict and sanitize datetime objects
            resource_dict = sanitize_for_json(dict(row._mapping))

            # Separate into OGM and B1G fields
            _, b1g_fields = _separate_ogm_and_b1g_fields(resource_dict)

            # Apply field filtering if fields parameter is provided
            if fields:
                b1g_fields = filter_resource_fields(b1g_fields, fields)
                logger.info(f"Filtered B1G metadata: {b1g_fields}")

            # Return only B1G block without JSON:API wrapping
            return JSONResponse(content=b1g_fields)
    except HTTPException:
        # Re-raise HTTP exceptions to maintain their status code
        raise
    except Exception:
        logger.error("Error getting B1G metadata for resource %s", id, exc_info=True)
        return JSONResponse(content={"error": "Failed to get B1G metadata"}, status_code=500)


def _get_metadata_url_for_format(
    resource_dict: dict, distribution_context: DistributionContext, format_key: str
) -> Optional[str]:
    """Resolve the metadata URL for a format from the resource's distributions."""
    uris = _FORMAT_URIS.get(format_key, [])
    link_service = LinkService(resource_dict, distribution_context=distribution_context)
    for uri in uris:
        if url := link_service._first_url(uri):
            return url
    return None


@router.get("/resources/{id}/metadata/display", response_class=HTMLResponse)
async def get_resource_metadata_display(
    id: str,
    format_key: str = Query(..., alias="format", description="Metadata format: iso, fgdc, or html"),
):
    """
    Fetch metadata from the resource's distribution URL, transform to HTML if needed,
    and return for in-page display. SSRF-safe: only URLs from the resource's own
    distributions are used.
    """
    fmt = format_key.lower().strip()
    if fmt not in ("iso", "fgdc", "html"):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid format '{format_key}'. Must be one of: iso, fgdc, html",
        )

    async with get_async_session() as session:
        query = select(resources).where(resources.c.id == id)
        result = await session.execute(query)
        row = result.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Resource not found")

        resource_dict = sanitize_for_json(dict(row._mapping))
        distribution_context = await fetch_distribution_context(id)
        url = _get_metadata_url_for_format(resource_dict, distribution_context, fmt)

    if not url:
        raise HTTPException(
            status_code=404,
            detail=f"No {fmt.upper()} metadata URL found for this resource",
        )

    try:
        timeout = aiohttp.ClientTimeout(total=METADATA_FETCH_TIMEOUT)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    raise HTTPException(
                        status_code=502,
                        detail=f"Metadata source returned status {resp.status}",
                    )
                content = await resp.text()
    except aiohttp.ClientError as e:
        logger.warning(f"Failed to fetch metadata from {url}: {e}")
        raise HTTPException(status_code=502, detail="Failed to fetch metadata from source") from e

    if fmt == "html":
        return HTMLResponse(content=content)

    try:
        if fmt == "iso":
            html = transform_iso_to_html(content)
        else:
            html = transform_fgdc_to_html(content)
        return HTMLResponse(content=html)
    except MetadataTransformError as e:
        logger.warning(f"Metadata transform failed for {id} ({fmt}): {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to transform metadata to HTML",
        ) from e
