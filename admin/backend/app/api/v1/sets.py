from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response

from app.api.dependencies import Database, RequestKey, mutation_header
from app.auth import Actor, require_permissions
from app.sets import membership, service, state
from app.sets.schemas import (
    SetActivityPage,
    SetCreate,
    SetEditorContract,
    SetID,
    SetPage,
    SetResponse,
    SetStateChange,
    SetStatePreview,
    SetStatus,
    SetUpdate,
)

router = APIRouter(
    prefix="/admin/sets",
    tags=["sets"],
)
Reader = Annotated[Actor, Depends(require_permissions(service.READ))]


contract_router = APIRouter(prefix="/admin/contracts", tags=["contracts"])


@contract_router.get(
    "/sets",
    response_model=SetEditorContract,
    operation_id="sets_get_contract",
    summary="Get Set editor contract",
)
async def contract(actor: Reader):
    """Current staff capabilities and server-owned form constraints; writes reauthorize."""
    service.authorize(actor)
    return {
        "create": actor.set_ids is None
        and {service.CREATE, service.SOURCE_USE}.issubset(actor.permissions),
        "update": service.UPDATE in actor.permissions,
        "activity_read": service.HISTORY in actor.permissions,
        "workflow_read": "workflows:read" in actor.permissions,
        "representative_update": {service.UPDATE, "resources:read"}.issubset(actor.permissions),
        "fields": SetCreate.model_json_schema()["properties"],
        "states": ["active", "inactive"]
        + (["retired"] if "sets:retired-read" in actor.permissions else []),
        "state_actions": state.options(actor),
    }


@router.get("", response_model=SetPage, operation_id="sets_list", summary="List sets")
async def index(
    actor: Reader,
    database: Database,
    q: Annotated[str, Query(max_length=200)] = "",
    offset: Annotated[int, Query(ge=0, le=1000000)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    source_id: SetID | None = None,
    status: SetStatus | None = None,
):
    """Staff-only Set search by ID/title; independent of Lifecycle grants."""
    return await service.list_sets(database, actor, q.strip(), offset, limit, source_id, status)


@router.get("/{set_id}", response_model=SetResponse, operation_id="sets_get", summary="Get a Set")
async def detail(set_id: SetID, actor: Reader, database: Database):
    """Read a Set, including internal notes, with an explicit Set read grant."""
    service.authorize(actor)
    async with database.connect() as connection:
        return await service.get_set(connection, actor, set_id)


@router.get(
    "/{set_id}/state-preview",
    response_model=SetStatePreview,
    operation_id="sets_state_preview",
    summary="Preview a Set state change",
)
async def state_preview(set_id: SetID, target: SetStatus, actor: Reader, database: Database):
    """Read the current version, consequences and unfinished Task count before confirmation."""
    return await state.preview(database, actor, set_id, target)


@router.put(
    "/{set_id}/state",
    response_model=SetResponse,
    dependencies=[Depends(mutation_header)],
    operation_id="sets_change_state",
    summary="Change Set state",
)
async def change_state(
    set_id: SetID,
    command: SetStateChange,
    request: Request,
    database: Database,
    key: RequestKey,
    actor: Reader,
):
    """Confirm a versioned change with a reason. Retirement and restoration need separate grants.

    Retirement rejects unfinished Tasks. Restore to inactive, then explicitly activate.
    Activation and recurring Task creation commit atomically with state evidence and a receipt.
    """
    return await state.change(
        database, actor, set_id, command, key, request.app.state.settings.app_version
    )


@router.put(
    "/{set_id}/representative",
    response_model=SetResponse,
    dependencies=[Depends(mutation_header)],
    operation_id="sets_change_representative",
    summary="Choose a Set representative Resource",
)
async def representative(
    set_id: SetID,
    command: membership.Representative,
    request: Request,
    database: Database,
    key: RequestKey,
    actor: Reader,
):
    """Choose an accessible Resource as a representative; does not change its managing Set."""
    return await membership.representative(
        database, actor, set_id, command, key, request.app.state.settings.app_version
    )


@router.post(
    "",
    response_model=SetResponse,
    status_code=201,
    responses={
        201: {
            "headers": {
                "Location": {"description": "Canonical read URL", "schema": {"type": "string"}}
            }
        }
    },
    dependencies=[Depends(mutation_header)],
    operation_id="sets_create",
    summary="Create a Set",
)
async def create(
    response: Response,
    command: SetCreate,
    request: Request,
    database: Database,
    key: RequestKey,
    actor: Annotated[Actor, Depends(require_permissions(service.READ, service.CREATE))],
):
    """Create a Source-owned Set and its Activity atomically.

    Requires human staff sets:read/create and sources:read/use. Both IDs are immutable.
    Workflow and interval labels do not authorize execution or establish schedules.
    """
    result = await service.mutate(
        database, actor, command, key, request.app.state.settings.app_version
    )
    response.headers["Location"] = f"/api/v1/admin/sets/{result.set_id}"
    return result


@router.patch(
    "/{set_id}",
    response_model=SetResponse,
    dependencies=[Depends(mutation_header)],
    operation_id="sets_update",
    summary="Update a Set",
)
async def edit(
    set_id: SetID,
    command: SetUpdate,
    request: Request,
    database: Database,
    key: RequestKey,
    actor: Annotated[Actor, Depends(require_permissions(service.READ, service.UPDATE))],
):
    """Update supplied fields only, comparing lock_version.

    Null clears endpoint_url; empty strings clear optional text fields. Omitted fields
    are preserved. Retry the identical request and Idempotency-Key after an uncertain result.
    State changes use PUT /{set_id}/state; retired Sets cannot be edited.
    """
    return await service.mutate(
        database, actor, command, key, request.app.state.settings.app_version, set_id
    )


@router.get(
    "/{set_id}/activity",
    response_model=SetActivityPage,
    operation_id="sets_list_activity",
    summary="List Set activity",
)
async def history(
    set_id: SetID,
    database: Database,
    actor: Annotated[Actor, Depends(require_permissions(service.READ, service.HISTORY))],
    offset: Annotated[int, Query(ge=0, le=1000000)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
):
    """Read staff-only Set evidence, ordered by occurrence time and ID descending."""
    return await service.history(database, actor, set_id, offset, limit)
