import os
from typing import Optional

from fastapi import Query, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy.sql import select

from app.api.v1.utils import create_response, sanitize_for_json
from app.services.citation_formats_service import CitationFormatsService
from app.services.citation_service import CitationService
from app.services.distribution_repository import fetch_distribution_context
from db.models import resources

from . import async_session, base_url, logger, router


def _geoportal_base_url() -> str:
    """Base URL for the Geoportal (resource pages). Strips /api/v1 from APPLICATION_URL."""
    url = os.getenv("GEOPORTAL_BASE_URL")
    if url:
        return url.rstrip("/")
    app_url = base_url.rstrip("/")
    for suffix in ("/api/v1", "/api/v1/"):
        if app_url.endswith(suffix):
            return app_url[: -len(suffix)].rstrip("/")
    return app_url


@router.get("/resources/{id}/citation")
async def get_resource_citation(
    request: Request,
    id: str,
    callback: Optional[str] = Query(None, description="JSONP callback name"),
):
    """Get the citation for a resource."""
    try:
        # Fetch resource to access metadata
        async with async_session() as session:
            query = select(resources).where(resources.c.id == id)
            result = await session.execute(query)
            row = result.fetchone()

            if not row:
                return JSONResponse(content={"error": "Resource not found"}, status_code=404)

            resource_dict = sanitize_for_json(dict(row._mapping))

        # Generate citations in all styles
        distribution_context = await fetch_distribution_context(id)
        citation_service = CitationService(resource_dict, distribution_context=distribution_context)
        citations = citation_service.get_all_citations()

        response_payload = {
            "id": id,
            "citation": citations["apa"],
            "citations": citations,
        }

        return create_response(response_payload, callback)
    except Exception as e:
        logger.error(f"Error getting citation for resource {id}: {str(e)}", exc_info=True)
        return JSONResponse(content={"error": str(e)}, status_code=500)


@router.get("/resources/{id}/citation/json-ld")
async def get_resource_citation_json_ld(id: str):
    """Get Schema.org JSON-LD metadata for citation tools (Zotero, Google Dataset Search)."""
    try:
        async with async_session() as session:
            query = select(resources).where(resources.c.id == id)
            result = await session.execute(query)
            row = result.fetchone()
            if not row:
                return JSONResponse(content={"error": "Resource not found"}, status_code=404)
            resource_dict = sanitize_for_json(dict(row._mapping))
        distribution_context = await fetch_distribution_context(id)
        service = CitationFormatsService(
            resource_dict,
            distribution_context=distribution_context,
            base_url=_geoportal_base_url(),
        )
        ld = service.to_json_ld(id)
        return JSONResponse(content=ld, media_type="application/ld+json")
    except Exception as e:
        logger.error(f"Error getting JSON-LD for resource {id}: {str(e)}", exc_info=True)
        return JSONResponse(content={"error": str(e)}, status_code=500)


@router.get("/resources/{id}/citation/ris")
async def get_resource_citation_ris(id: str):
    """Get RIS format for EndNote, Zotero, Mendeley import."""
    try:
        async with async_session() as session:
            query = select(resources).where(resources.c.id == id)
            result = await session.execute(query)
            row = result.fetchone()
            if not row:
                return JSONResponse(content={"error": "Resource not found"}, status_code=404)
            resource_dict = sanitize_for_json(dict(row._mapping))
        distribution_context = await fetch_distribution_context(id)
        service = CitationFormatsService(
            resource_dict,
            distribution_context=distribution_context,
            base_url=_geoportal_base_url(),
        )
        ris = service.to_ris(id)
        return PlainTextResponse(
            content=ris,
            media_type="application/x-research-info-systems",
            headers={"Content-Disposition": f'attachment; filename="{id}.ris"'},
        )
    except Exception as e:
        logger.error(f"Error getting RIS for resource {id}: {str(e)}", exc_info=True)
        return JSONResponse(content={"error": str(e)}, status_code=500)


@router.get("/resources/{id}/citation/bibtex")
async def get_resource_citation_bibtex(id: str):
    """Get BibTeX format for LaTeX and citation tools."""
    try:
        async with async_session() as session:
            query = select(resources).where(resources.c.id == id)
            result = await session.execute(query)
            row = result.fetchone()
            if not row:
                return JSONResponse(content={"error": "Resource not found"}, status_code=404)
            resource_dict = sanitize_for_json(dict(row._mapping))
        distribution_context = await fetch_distribution_context(id)
        service = CitationFormatsService(
            resource_dict,
            distribution_context=distribution_context,
            base_url=_geoportal_base_url(),
        )
        bib = service.to_bibtex(id)
        return PlainTextResponse(
            content=bib,
            media_type="application/x-bibtex",
            headers={"Content-Disposition": f'attachment; filename="{id}.bib"'},
        )
    except Exception as e:
        logger.error(f"Error getting BibTeX for resource {id}: {str(e)}", exc_info=True)
        return JSONResponse(content={"error": str(e)}, status_code=500)
