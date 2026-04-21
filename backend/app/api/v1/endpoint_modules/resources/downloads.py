from typing import Optional

import requests
from fastapi import HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.sql import select

from app.api.v1.utils import create_response, sanitize_for_json
from app.services.distribution_repository import fetch_distribution_context
from app.services.download_service import DownloadService
from db.models import resources

from . import async_session, logger, router


@router.get("/resources/{id}/downloads")
async def get_resource_downloads(
    request: Request,
    id: str,
    callback: Optional[str] = Query(None, description="JSONP callback name"),
):
    """Get the download options for a resource."""
    try:
        # Fetch resource to access metadata
        async with async_session() as session:
            query = select(resources).where(resources.c.id == id)
            result = await session.execute(query)
            row = result.fetchone()

            if not row:
                return JSONResponse(content={"error": "Resource not found"}, status_code=404)

            resource_dict = sanitize_for_json(dict(row._mapping))

        # Generate download options using DownloadService
        distribution_context = await fetch_distribution_context(id)
        download_service = DownloadService(resource_dict, distribution_context=distribution_context)
        downloads = await download_service.get_download_options_with_bridge_asset_downloads()

        response_payload = {
            "id": id,
            "downloads": downloads,
        }

        return create_response(response_payload, callback)
    except Exception:
        logger.error("Error getting downloads for resource %s", id, exc_info=True)
        return JSONResponse(content={"error": "Failed to get downloads"}, status_code=500)


@router.get("/resources/{id}/downloads/generated/{download_type}")
async def prepare_generated_download(id: str, download_type: str):
    """Prepare a generated download and return its API file URL."""
    try:
        async with async_session() as session:
            query = select(resources).where(resources.c.id == id)
            result = await session.execute(query)
            row = result.fetchone()
            if not row:
                return JSONResponse(content={"error": "Resource not found"}, status_code=404)
            resource_dict = sanitize_for_json(dict(row._mapping))

        distribution_context = await fetch_distribution_context(id)
        download_service = DownloadService(resource_dict, distribution_context=distribution_context)
        payload = await download_service.ensure_generated_download(download_type)
        return JSONResponse(content=payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except requests.HTTPError as exc:
        status_code = getattr(getattr(exc, "response", None), "status_code", 502)
        raise HTTPException(
            status_code=502,
            detail=f"Upstream service failed while preparing '{download_type}' ({status_code})",
        ) from exc
    except Exception as exc:
        logger.error(
            "Failed to prepare generated download for resource %s (%s)",
            id,
            download_type,
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Failed to prepare generated download") from exc


@router.get("/resources/{id}/downloads/generated/{download_type}/file")
async def fetch_generated_download_file(id: str, download_type: str):
    """
    Return the generated file. If it does not exist yet, generate it first.
    """
    try:
        async with async_session() as session:
            query = select(resources).where(resources.c.id == id)
            result = await session.execute(query)
            row = result.fetchone()
            if not row:
                return JSONResponse(content={"error": "Resource not found"}, status_code=404)
            resource_dict = sanitize_for_json(dict(row._mapping))

        distribution_context = await fetch_distribution_context(id)
        download_service = DownloadService(resource_dict, distribution_context=distribution_context)
        payload = await download_service.ensure_generated_download(download_type)

        file_path = payload.get("file_path")
        file_name = payload.get("file_name")
        media_type = payload.get("content_type", "application/octet-stream")
        if not isinstance(file_path, str) or not isinstance(file_name, str):
            raise HTTPException(status_code=500, detail="Generated download payload is invalid")

        return FileResponse(
            path=file_path,
            media_type=media_type if isinstance(media_type, str) else "application/octet-stream",
            filename=file_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except requests.HTTPError as exc:
        status_code = getattr(getattr(exc, "response", None), "status_code", 502)
        raise HTTPException(
            status_code=502,
            detail=f"Upstream service failed while preparing '{download_type}' ({status_code})",
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "Failed to fetch generated download file for resource %s (%s)",
            id,
            download_type,
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Failed to fetch generated download") from exc
