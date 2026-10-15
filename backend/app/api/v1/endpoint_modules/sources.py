"""Public Source discovery through the canonical GEOMG read boundary."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from app.services.source_projection import (
    ProjectionFailure,
    SourceAdapter,
    SourceDetail,
    SourceID,
    SourcePage,
    SourceResources,
)

router = APIRouter()
Offset = Annotated[int, Query(ge=0, le=1000000)]
Limit = Annotated[int, Query(ge=1, le=500)]


def source_adapter():
    return SourceAdapter()


Adapter = Annotated[SourceAdapter, Depends(source_adapter)]


async def read(adapter, model, **kwargs):
    try:
        result = await adapter.read(model, **kwargs)
        return JSONResponse(result.model_dump(mode="json"), headers={"Cache-Control": "no-store"})
    except ProjectionFailure as exc:
        return JSONResponse(
            {"detail": "Source not found" if exc.status == 404 else "Source service unavailable"},
            status_code=exc.status,
            headers={"Cache-Control": "no-store"},
        )


@router.get("/sources", response_model=SourcePage)
async def list_sources(
    adapter: Adapter,
    q: Annotated[str, Query(max_length=200)] = "",
    offset: Offset = 0,
    limit: Limit = 100,
):
    """Current Source cards, including empty Sources; query matches Source title/ID.

    Results use canonical publication/suppression counts, not a local delivery receipt.
    No cache or Resource hydration is applied. Failures are not empty result sets.
    """
    return await read(adapter, SourcePage, q=q.strip(), offset=offset, limit=limit)


@router.get("/sources/{source_id}", response_model=SourceDetail)
async def get_source(source_id: SourceID, adapter: Adapter):
    """Public Source fields only; independent of Lifecycle identity."""
    return await read(adapter, SourceDetail, source_id=source_id)


@router.get("/sources/{source_id}/resources", response_model=SourceResources)
async def source_resources(
    source_id: SourceID, adapter: Adapter, offset: Offset = 0, limit: Limit = 100
):
    """Published, unsuppressed Resource references and counts from one upstream snapshot.

    Restricted data can have public catalog metadata. These are ID/title references,
    not Resource documents or downloads; local Resource delivery is not implied.
    Separate pages are live reads rather than a durable multi-page snapshot.
    """
    return await read(
        adapter, SourceResources, source_id=source_id, resources=True, offset=offset, limit=limit
    )
