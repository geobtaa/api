from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import select

from app.api.contracts import WorkflowContract
from app.api.dependencies import Database, RequestKey, mutation_header
from app.auth import Actor, require_permissions
from app.sets.schemas import SetID
from app.workflows import service
from app.workflows.models import process_types
from app.workflows.schemas import (
    CONFIG_FIELDS,
    Activation,
    Configuration,
    DraftUpdate,
    VersionCommand,
    VersionPage,
    VersionResponse,
    WorkflowCreate,
    WorkflowPage,
    WorkflowResponse,
)

router = APIRouter(
    prefix="/admin/workflows",
    tags=["workflows"],
)
Reader = Annotated[Actor, Depends(require_permissions("sets:read", service.READ))]


contract_router = APIRouter(prefix="/admin/contracts", tags=["contracts"])


@contract_router.get(
    "/workflows",
    response_model=WorkflowContract,
    operation_id="workflows_get_contract",
    summary="Get Workflow editor contract",
)
async def contract(actor: Reader, database: Database):
    """Controlled definitions and version-one configuration guidance; no arbitrary scripting."""
    async with database.connect() as connection:
        rows = (
            (await connection.execute(select(process_types).order_by(process_types.c.key)))
            .mappings()
            .all()
        )
    return {
        "process_types": [
            {**row, "configuration_fields": CONFIG_FIELDS[row["key"]]} for row in rows
        ],
        "configuration_schema": Configuration.model_json_schema(),
        "maximum_processes": 100,
        "configuration_schema_version": 1,
        "can_create": actor.kind == "user" and service.CHANGE in actor.permissions,
    }


@router.get(
    "", response_model=WorkflowPage, operation_id="workflows_list", summary="List workflows"
)
async def index(
    set_id: SetID,
    actor: Reader,
    database: Database,
    offset: Annotated[int, Query(ge=0, le=1000000)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
):
    return await service.list_workflows(database, actor, set_id, offset, limit)


@router.get(
    "/{workflow_id}",
    response_model=WorkflowResponse,
    operation_id="workflows_get",
    summary="Get a Workflow",
)
async def detail(workflow_id: UUID, actor: Reader, database: Database):
    async with database.connect() as connection:
        connection = await connection.execution_options(isolation_level="REPEATABLE READ")
        async with connection.begin():
            return await service.detail(connection, actor, workflow_id)


@router.get(
    "/{workflow_id}/versions",
    response_model=VersionPage,
    operation_id="workflows_list_versions",
    summary="List Workflow versions",
)
async def history(
    workflow_id: UUID,
    actor: Reader,
    database: Database,
    offset: Annotated[int, Query(ge=0, le=1000000)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
):
    """Preserved definitions, newest first, including superseded versions for pinned consumers."""
    return await service.history(database, actor, workflow_id, offset, limit)


@router.get(
    "/{workflow_id}/versions/{version_id}",
    response_model=VersionResponse,
    operation_id="workflows_pinned_version",
    summary="Get pinned Workflow version",
)
async def pinned_version(workflow_id: UUID, version_id: UUID, actor: Reader, database: Database):
    """Read an exact preserved version; never substitute the latest definition."""
    async with database.connect() as connection:
        connection = await connection.execution_options(isolation_level="REPEATABLE READ")
        async with connection.begin():
            return await service.get_version(connection, actor, workflow_id, version_id)


@router.post(
    "",
    response_model=WorkflowResponse,
    status_code=201,
    responses={
        201: {
            "headers": {
                "Location": {"description": "Canonical read URL", "schema": {"type": "string"}}
            }
        }
    },
    dependencies=[Depends(mutation_header)],
    operation_id="workflows_create",
    summary="Create a Workflow",
)
async def create(
    response: Response,
    command: WorkflowCreate,
    actor: Reader,
    database: Database,
    key: RequestKey,
    request: Request,
):
    result = await service.mutate(
        database, actor, "create", command, key, request.app.state.settings.app_version
    )
    response.headers["Location"] = f"/api/v1/admin/workflows/{result.workflow_id}"
    return result


@router.put(
    "/{workflow_id}/draft",
    response_model=WorkflowResponse,
    dependencies=[Depends(mutation_header)],
    operation_id="workflows_update_draft",
    summary="Replace Workflow draft",
)
async def update_draft(
    workflow_id: UUID,
    command: DraftUpdate,
    actor: Reader,
    database: Database,
    key: RequestKey,
    request: Request,
):
    """Replace the draft definition with optimistic concurrency and atomic evidence."""
    return await service.mutate(
        database, actor, "update", command, key, request.app.state.settings.app_version, workflow_id
    )


@router.post(
    "/{workflow_id}/draft",
    response_model=WorkflowResponse,
    dependencies=[Depends(mutation_header)],
    operation_id="workflows_create_draft",
    summary="Create Workflow draft",
)
async def clone(
    workflow_id: UUID,
    command: VersionCommand,
    actor: Reader,
    database: Database,
    key: RequestKey,
    request: Request,
):
    return await service.mutate(
        database, actor, "clone", command, key, request.app.state.settings.app_version, workflow_id
    )


@router.post(
    "/{workflow_id}/activate",
    response_model=WorkflowResponse,
    dependencies=[Depends(mutation_header)],
    operation_id="workflows_activate",
    summary="Activate Workflow version",
)
async def activate(
    workflow_id: UUID,
    command: Activation,
    actor: Reader,
    database: Database,
    key: RequestKey,
    request: Request,
):
    """Atomically activate the exact draft and supersede the prior version. Does not start work."""
    return await service.mutate(
        database,
        actor,
        "activate",
        command,
        key,
        request.app.state.settings.app_version,
        workflow_id,
    )
