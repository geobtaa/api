from fastapi import HTTPException
from fastapi.responses import JSONResponse

from app.api.schemas import DataDictionaryListResponse
from app.api.v1.utils import sanitize_for_json
from app.services.data_dictionary_repository import (
    fetch_resource_data_dictionaries,
    serialize_resource_data_dictionaries,
)

from . import get_async_session, logger, router


@router.get("/resources/{id}/data-dictionaries", response_model=DataDictionaryListResponse)
async def get_resource_data_dictionaries(id: str):
    """Get data dictionaries for a single resource."""
    try:
        async with get_async_session() as session:
            dictionaries = await fetch_resource_data_dictionaries(id, session=session)
            payload = serialize_resource_data_dictionaries(dictionaries)
            return JSONResponse(content=sanitize_for_json(payload))
    except HTTPException:
        raise
    except Exception:
        logger.error("Error getting data dictionaries for resource %s", id, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get data dictionaries") from None
