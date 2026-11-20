"""Shared descriptive workflow vocabulary; separate from executable Workflow versions."""

from pydantic import BaseModel
from sqlalchemy import Column, String, Table, Text, select

from app.persistence import metadata


class WorkflowCatalogEntry(BaseModel):
    workflow_id: str
    label: str
    description: str
    acquisition_mode: str


catalog = Table(
    "workflow_catalog",
    metadata,
    Column("workflow_id", String(128), primary_key=True),
    Column("label", String(250), nullable=False),
    Column("description", Text, nullable=False),
    Column("acquisition_mode", String(64), nullable=False),
)


async def list_catalog(engine):
    async with engine.connect() as connection:
        return [
            dict(row)
            for row in (
                await connection.execute(
                    select(catalog).order_by(catalog.c.label, catalog.c.workflow_id)
                )
            ).mappings()
        ]


async def require_catalog(connection, workflow_id):
    if workflow_id is not None and not await connection.scalar(
        select(catalog.c.workflow_id).where(catalog.c.workflow_id == workflow_id)
    ):
        from app.sets.service import DomainError

        raise DomainError(422, "unknown_workflow", "Choose a workflow from the catalog")
