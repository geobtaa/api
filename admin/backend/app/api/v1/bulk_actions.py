from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request

from app.api.dependencies import Database, RequestKey, mutation_header
from app.auth import Actor, require_permissions
from app.resources import bulk
from app.resources.bulk_schemas import BulkDetail, BulkEdit, BulkHistory, BulkId, Confirm

router = APIRouter(prefix="/admin/resource-bulk-actions", tags=["resources"])
Staff = Annotated[Actor, Depends(require_permissions("resources:bulk-update"))]
Offset = Annotated[int, Query(ge=0)]
Limit = Annotated[int, Query(ge=1, le=100)]
mutation = [Depends(mutation_header)]


@router.post(
    "",
    response_model=BulkId,
    status_code=201,
    dependencies=mutation,
    operation_id="resource_bulk_actions_preview",
    summary="Preview a bulk metadata edit",
)
async def preview(command: BulkEdit, actor: Staff, database: Database, key: RequestKey):
    """Snapshot per-Resource differences for a saved selection. No Resource is changed."""
    return await bulk.preview(database, actor, key, command=command)


@router.get(
    "",
    response_model=BulkHistory,
    operation_id="resource_bulk_actions_list",
    summary="List my bulk actions",
)
async def history(actor: Staff, database: Database, offset: Offset = 0, limit: Limit = 25):
    return await bulk.history(database, actor, offset, limit)


@router.get(
    "/{action_id}",
    response_model=BulkDetail,
    operation_id="resource_bulk_actions_get",
    summary="Review bulk metadata changes",
)
async def detail(
    action_id: UUID, actor: Staff, database: Database, offset: Offset = 0, limit: Limit = 25
):
    return await bulk.detail(database, actor, action_id, offset, limit)


@router.put(
    "/{action_id}/confirmation",
    response_model=BulkId,
    dependencies=mutation,
    operation_id="resource_bulk_actions_confirm",
    summary="Confirm a previewed bulk action",
)
async def confirm(
    action_id: UUID, command: Confirm, actor: Staff, database: Database, request: Request
):
    """Confirm once per preview after rechecking scope, versions and dependencies."""
    return await bulk.confirm(database, actor, action_id, request.app.state.settings.app_version)


@router.post(
    "/{action_id}/reversions",
    response_model=BulkId,
    status_code=201,
    dependencies=mutation,
    operation_id="resource_bulk_actions_revert_preview",
    summary="Preview reversal of my bulk edit",
)
async def revert(action_id: UUID, actor: Staff, database: Database, key: RequestKey):
    """Prepare a new versioned action using the recorded prior values of changed Resources."""
    return await bulk.preview(database, actor, key, reverts=action_id)
