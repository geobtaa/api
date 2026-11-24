"""Shared descriptive workflow lookup for Set forms."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import Database
from app.auth import Actor, get_current_actor
from app.workflows.catalog import WorkflowCatalogEntry, list_catalog

router = APIRouter(prefix="/admin/workflow-catalog", tags=["workflows"])


@router.get(
    "",
    response_model=list[WorkflowCatalogEntry],
    operation_id="workflow_catalog_list",
    summary="List workflow catalog",
)
async def index(database: Database, actor: Annotated[Actor, Depends(get_current_actor)]):
    if actor.kind != "user" or "sets:read" not in actor.permissions:
        raise HTTPException(403, "Staff Set read permission required")
    return await list_catalog(database)
