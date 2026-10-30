from typing import Optional

from fastapi import HTTPException, Query, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy.sql import select

from app.api.schemas import ResourceCitationResponse, SchemaOrgCitationResponse
from app.api.v1.utils import create_response, sanitize_for_json
from app.services.citation_formats_service import CitationFormatsService
from app.services.citation_service import CitationService
from app.services.distribution_repository import fetch_distribution_context
from app.services.linked_data import geoportal_base_url
from db.models import resources

from . import async_session, logger, router


class JSONLDResponse(JSONResponse):
    """Advertise the JSON-LD media type in both HTTP and OpenAPI."""

    media_type = "application/ld+json"


def _geoportal_base_url() -> str:
    """Use the same canonical identity as embedded JSON-LD."""
    return geoportal_base_url()


@router.get("/resources/{id}/citation", response_model=ResourceCitationResponse)
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
                raise HTTPException(status_code=404, detail="Resource not found")

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
    except HTTPException:
        raise
    except Exception:
        logger.error("Error getting citation for resource %s", id, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get citation") from None


@router.get(
    "/resources/{id}/citation/json-ld",
    response_model=SchemaOrgCitationResponse,
    response_class=JSONLDResponse,
)
async def get_resource_citation_json_ld(id: str):
    """Get Schema.org JSON-LD metadata for citation tools (Zotero, Google Dataset Search)."""
    try:
        async with async_session() as session:
            query = select(resources).where(resources.c.id == id)
            result = await session.execute(query)
            row = result.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Resource not found")
            resource_dict = sanitize_for_json(dict(row._mapping))
        distribution_context = await fetch_distribution_context(id)
        service = CitationFormatsService(
            resource_dict,
            distribution_context=distribution_context,
            base_url=_geoportal_base_url(),
        )
        ld = service.to_json_ld(id)
        return JSONLDResponse(content=ld)
    except HTTPException:
        raise
    except Exception:
        logger.error("Error getting JSON-LD for resource %s", id, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get citation metadata") from None


@router.get("/resources/{id}/citation/ris", response_class=PlainTextResponse)
async def get_resource_citation_ris(id: str):
    """Get RIS format for EndNote, Zotero, Mendeley import."""
    try:
        async with async_session() as session:
            query = select(resources).where(resources.c.id == id)
            result = await session.execute(query)
            row = result.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Resource not found")
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
    except HTTPException:
        raise
    except Exception:
        logger.error("Error getting RIS for resource %s", id, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get RIS citation") from None


@router.get("/resources/{id}/citation/bibtex", response_class=PlainTextResponse)
async def get_resource_citation_bibtex(id: str):
    """Get BibTeX format for LaTeX and citation tools."""
    try:
        async with async_session() as session:
            query = select(resources).where(resources.c.id == id)
            result = await session.execute(query)
            row = result.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Resource not found")
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
    except HTTPException:
        raise
    except Exception:
        logger.error("Error getting BibTeX for resource %s", id, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get BibTeX citation") from None
