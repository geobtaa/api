"""Resourceful Work reads and atomic Set maintenance/Task commands."""

from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel
from sqlalchemy import or_, select

from app.api.dependencies import Database, RequestKey, mutation_header
from app.auth import Actor, require_permissions
from app.domain import DomainError
from app.identity.models import accounts
from app.persistence import actors
from app.sets.service import get_set
from app.work import service
from app.work.models import maintenance, periods
from app.work.schemas import (
    Assignee,
    EventPage,
    MaintenanceResponse,
    MaintenanceUpdate,
    PeriodCreate,
    PeriodResponse,
    RecurringType,
    SetID,
    TaskCompletion,
    TaskCreate,
    TaskPage,
    TaskResponse,
    TaskUpdate,
    WorkReport,
    WorkType,
)

router = APIRouter(prefix="/admin", tags=["tasks"])
maintenance_router = APIRouter(prefix="/admin/sets", tags=["sets"])
period_router = APIRouter(prefix="/admin/work-periods", tags=["work-periods"])
contract_router = APIRouter(prefix="/admin/contracts", tags=["contracts"])
Reader = Annotated[Actor, Depends(require_permissions("tasks:read"))]
Offset = Annotated[int, Query(ge=0, le=1000000)]
Limit = Annotated[int, Query(ge=1, le=500)]


class WorkContract(BaseModel):
    create: bool
    update: bool
    complete: bool
    configure: bool
    report: bool
    work_types: list[str]
    statuses: list[str]


@contract_router.get(
    "/tasks",
    response_model=WorkContract,
    operation_id="tasks_contract",
    summary="Get Task editor contract",
)
async def contract(actor: Reader):
    service.authorize(actor)
    return {
        "create": "tasks:create" in actor.permissions,
        "update": "tasks:update" in actor.permissions,
        "complete": "tasks:complete" in actor.permissions,
        "configure": {"work:configure", "tasks:create"}.issubset(actor.permissions),
        "report": "work:report" in actor.permissions,
        "work_types": ["review", "ingest", "other"],
        "statuses": ["open", "in_progress", "blocked", "completed", "cancelled"],
    }


@router.get("/tasks", response_model=TaskPage, operation_id="tasks_list", summary="List Tasks")
async def index(
    actor: Reader,
    database: Database,
    offset: Offset = 0,
    limit: Limit = 50,
    set_id: SetID | None = None,
    source_id: SetID | None = None,
    status: Literal["pending", "open", "in_progress", "blocked", "completed", "cancelled"]
    | None = "pending",
    work_type: WorkType | None = None,
    assignee_id: UUID | None = None,
    unassigned: bool = False,
    q: Annotated[str, Query(max_length=200)] = "",
    due_from: date | None = None,
    due_to: date | None = None,
    completed_from: date | None = None,
    completed_to: date | None = None,
    calendar_from: date | None = None,
    calendar_to: date | None = None,
):
    """Queue, Calendar and Completed share records and authorization.

    Calendar filters planned_on, falling back to due_on. Completion filters use
    actual completion dates in UTC, independent of due dates and entry timestamps.
    """
    return await service.page(
        database,
        actor,
        offset,
        limit,
        set_id=set_id,
        source_id=source_id,
        status=status,
        work_type=work_type,
        assignee_id=assignee_id,
        unassigned=unassigned,
        q=q.strip(),
        due_from=due_from,
        due_to=due_to,
        completed_from=completed_from,
        completed_to=completed_to,
        calendar_from=calendar_from,
        calendar_to=calendar_to,
    )


@router.get(
    "/tasks/report",
    response_model=WorkReport,
    operation_id="tasks_report",
    summary="Summarize completed work",
)
async def report(
    actor: Reader,
    database: Database,
    starts_on: date,
    ends_on: date,
    group_by: Literal["source", "set", "work_type", "completed_by"] = "set",
    offset: Offset = 0,
    limit: Limit = 50,
    set_id: SetID | None = None,
    source_id: SetID | None = None,
    work_type: WorkType | None = None,
    assignee_id: UUID | None = None,
    q: Annotated[str, Query(max_length=200)] = "",
    unassigned: bool = False,
):
    return await service.report(
        database,
        actor,
        starts_on,
        ends_on,
        group_by,
        offset,
        limit,
        set_id=set_id,
        source_id=source_id,
        work_type=work_type,
        assignee_id=assignee_id,
        q=q,
        unassigned=unassigned,
    )


@router.get(
    "/tasks/assignees",
    response_model=list[Assignee],
    operation_id="tasks_assignees",
    summary="Find staff Task assignees",
)
async def assignees(
    actor: Reader,
    database: Database,
    q: Annotated[str, Query(max_length=200)] = "",
    limit: Limit = 50,
    set_id: SetID | None = None,
):
    service.authorize(actor)
    async with database.connect() as connection:
        if set_id is not None:
            await get_set(connection, actor, set_id)
        query = (
            select(actors.c.id.label("actor_id"), actors.c.display_name)
            .select_from(actors.outerjoin(accounts))
            .where(
                actors.c.kind == "user",
                actors.c.display_name.icontains(q, autoescape=True),
                or_(
                    (actors.c.subject_key == actor.actor_id)
                    & service.ASSIGNEE_PERMISSIONS.issubset(actor.permissions),
                    accounts.c.active
                    & service.assignee_permissions(actors.c.id)
                    & service.assignee_scope(actors.c.id, actor, set_id),
                ),
            )
            .order_by(actors.c.display_name, actors.c.id)
            .limit(limit)
        )
        return (await connection.execute(query)).mappings().all()


@router.post(
    "/tasks",
    response_model=TaskResponse,
    status_code=201,
    dependencies=[Depends(mutation_header)],
    operation_id="tasks_create",
    summary="Create a Task",
)
async def create(
    command: TaskCreate, actor: Reader, database: Database, key: RequestKey, response: Response
):
    result = await service.create(database, actor, command, key)
    response.headers["Location"] = f"/api/v1/admin/tasks/{result.task_id}"
    return result


@router.get(
    "/tasks/{task_id}", response_model=TaskResponse, operation_id="tasks_get", summary="Get a Task"
)
async def detail(task_id: UUID, actor: Reader, database: Database):
    async with database.connect() as connection:
        return await service.get_task(connection, actor, task_id)


@router.patch(
    "/tasks/{task_id}",
    response_model=TaskResponse,
    dependencies=[Depends(mutation_header)],
    operation_id="tasks_update",
    summary="Update a Task",
)
async def edit(
    task_id: UUID, command: TaskUpdate, actor: Reader, database: Database, key: RequestKey
):
    return await service.edit(database, actor, task_id, command, key)


@router.post(
    "/tasks/{task_id}/completion",
    response_model=TaskResponse,
    dependencies=[Depends(mutation_header)],
    operation_id="tasks_complete",
    summary="Complete a Task occurrence",
)
async def complete(
    task_id: UUID, command: TaskCompletion, actor: Reader, database: Database, key: RequestKey
):
    """Preserve completion evidence and atomically create the next enabled recurring occurrence."""
    return await service.complete(database, actor, task_id, command, key)


@router.get(
    "/tasks/{task_id}/activity",
    response_model=EventPage,
    operation_id="tasks_activity",
    summary="Read Task history",
)
async def history(
    task_id: UUID, actor: Reader, database: Database, offset: Offset = 0, limit: Limit = 50
):
    return await service.history(database, actor, task_id, offset, limit)


@maintenance_router.get(
    "/{set_id}/maintenance",
    response_model=list[MaintenanceResponse],
    operation_id="sets_maintenance",
    summary="Read Set maintenance settings",
)
async def maintenance_settings(set_id: SetID, actor: Reader, database: Database):
    service.authorize(actor)
    async with database.connect() as connection:
        await get_set(connection, actor, set_id)
        return (
            (
                await connection.execute(
                    select(maintenance)
                    .where(maintenance.c.set_id == set_id)
                    .order_by(maintenance.c.work_type)
                )
            )
            .mappings()
            .all()
        )


@maintenance_router.put(
    "/{set_id}/maintenance/{work_type}",
    response_model=MaintenanceResponse,
    dependencies=[Depends(mutation_header)],
    operation_id="sets_configure_maintenance",
    summary="Configure recurring Set work",
)
async def configure(
    request: Request,
    set_id: SetID,
    work_type: RecurringType,
    command: MaintenanceUpdate,
    actor: Reader,
    database: Database,
    key: RequestKey,
):
    return await service.configure(
        database, actor, set_id, work_type, command, key, request.app.state.settings.app_version
    )


@period_router.get(
    "",
    response_model=list[PeriodResponse],
    operation_id="work_periods_list",
    summary="List named reporting periods",
)
async def period_list(actor: Reader, database: Database, offset: Offset = 0, limit: Limit = 50):
    service.authorize(actor)
    async with database.connect() as connection:
        return (
            (
                await connection.execute(
                    select(periods)
                    .order_by(periods.c.starts_on.desc(), periods.c.period_id)
                    .offset(offset)
                    .limit(limit)
                )
            )
            .mappings()
            .all()
        )


@period_router.get(
    "/{period_id}",
    response_model=PeriodResponse,
    operation_id="work_periods_get",
    summary="Get a named reporting period",
)
async def period_detail(period_id: UUID, actor: Reader, database: Database):
    service.authorize(actor)
    async with database.connect() as connection:
        result = (
            (await connection.execute(select(periods).where(periods.c.period_id == period_id)))
            .mappings()
            .first()
        )
        if result is None:
            raise DomainError(404, "not_found", "Reporting period not found")
        return result


@period_router.post(
    "",
    response_model=PeriodResponse,
    status_code=201,
    dependencies=[Depends(mutation_header)],
    operation_id="work_periods_create",
    summary="Save a named reporting period",
)
async def create_period(
    command: PeriodCreate, actor: Reader, database: Database, key: RequestKey, response: Response
):
    result = await service.create_period(database, actor, command, key)
    response.headers["Location"] = f"/api/v1/admin/work-periods/{result.period_id}"
    return result
