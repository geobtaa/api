from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response

from app.api.dependencies import Database, RequestKey, mutation_header
from app.auth import Actor, require_permissions
from app.sources import activity as source_activity
from app.sources import service
from app.sources.schemas import (
    SourceActivityCreate,
    SourceActivityPage,
    SourceActivityResponse,
    SourceCreate,
    SourceEditorContract,
    SourceID,
    SourcePage,
    SourceResponse,
    SourceUpdate,
)

router = APIRouter(
    prefix="/admin/sources",
    tags=["sources"],
)
Reader = Annotated[Actor, Depends(require_permissions(service.READ))]


contract_router = APIRouter(prefix="/admin/contracts", tags=["contracts"])


@contract_router.get(
    "/sources",
    response_model=SourceEditorContract,
    operation_id="sources_get_contract",
    summary="Get Source editor contract",
)
async def contract(actor: Reader):
    """Current staff capabilities and server-owned form constraints; writes reauthorize."""
    service.authorize(actor)
    return {
        "create": service.CREATE in actor.permissions,
        "update": service.UPDATE in actor.permissions,
        "activity_read": source_activity.READ in actor.permissions,
        "set_read": "sets:read" in actor.permissions,
        "resource_read": "resources:read" in actor.permissions,
        "fields": SourceCreate.model_json_schema()["properties"],
    }


@router.get("", response_model=SourcePage, operation_id="sources_list", summary="List sources")
async def index(
    actor: Reader,
    database: Database,
    q: Annotated[str, Query(max_length=200)] = "",
    offset: Annotated[int, Query(ge=0, le=1000000)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
):
    """Staff-only Source search by ID, title, or legacy code."""
    return await service.list_sources(database, actor, q.strip(), offset, limit)


@router.get(
    "/{source_id}",
    response_model=SourceResponse,
    operation_id="sources_get",
    summary="Get a Source",
)
async def detail(source_id: SourceID, actor: Reader, database: Database):
    """Read a Source, including internal notes, with an explicit Source read grant."""
    service.authorize(actor)
    async with database.connect() as connection:
        return await service.get_source(connection, actor, source_id)


@router.post(
    "",
    response_model=SourceResponse,
    status_code=201,
    responses={
        201: {
            "headers": {
                "Location": {"description": "Canonical read URL", "schema": {"type": "string"}}
            }
        }
    },
    dependencies=[Depends(mutation_header)],
    operation_id="sources_create",
    summary="Create a Source",
)
async def create(
    response: Response,
    command: SourceCreate,
    request: Request,
    database: Database,
    key: RequestKey,
    actor: Annotated[Actor, Depends(require_permissions(service.READ, service.CREATE))],
):
    """Create an independent Source and its Activity atomically; IDs are immutable.

    Requires human staff sources:read and sources:create, not Lifecycle membership.
    Supply an inventory ID or omit source_id to generate one. No publication is implied.
    """
    result = await service.mutate(
        database, actor, command, key, request.app.state.settings.app_version
    )
    response.headers["Location"] = f"/api/v1/admin/sources/{result.source_id}"
    return result


@router.patch(
    "/{source_id}",
    response_model=SourceResponse,
    dependencies=[Depends(mutation_header)],
    operation_id="sources_update",
    summary="Update a Source",
)
async def edit(
    source_id: SourceID,
    command: SourceUpdate,
    request: Request,
    database: Database,
    key: RequestKey,
    actor: Annotated[Actor, Depends(require_permissions(service.READ, service.UPDATE))],
):
    """Update supplied fields only, comparing lock_version.

    Null clears landing_page; empty strings clear description/admin_notes. Omitted fields
    are preserved. Retry the identical request and Idempotency-Key after an uncertain result.
    """
    return await service.mutate(
        database, actor, command, key, request.app.state.settings.app_version, source_id
    )


@router.get(
    "/{source_id}/activity",
    response_model=SourceActivityPage,
    operation_id="sources_list_activity",
    summary="List Source activity",
)
async def history(
    source_id: SourceID,
    database: Database,
    actor: Annotated[Actor, Depends(require_permissions(service.READ, source_activity.READ))],
    offset: Annotated[int, Query(ge=0, le=1000000)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
):
    """Read staff-only Source evidence, ordered by occurrence time and ID descending."""
    return await source_activity.history(database, actor, source_id, offset, limit)


@router.post(
    "/{source_id}/activity",
    response_model=SourceActivityResponse,
    status_code=201,
    dependencies=[Depends(mutation_header)],
    operation_id="sources_record_activity",
    summary="Record activity",
)
async def record_activity(
    source_id: SourceID,
    command: SourceActivityCreate,
    request: Request,
    database: Database,
    key: RequestKey,
    actor: Annotated[Actor, Depends(require_permissions(service.READ, source_activity.CREATE))],
):
    """Record staff-reported review/harvest work directly against a Source.

    This attests work already performed; it does not execute work, publish Resources,
    or alter Lifecycle schedules. Actor, recording time, and origin are server-owned.
    Replay the same body/key after uncertain results. History requires its own read grant.
    """
    return await source_activity.record(
        database, actor, source_id, command, key, request.app.state.settings.app_version
    )
