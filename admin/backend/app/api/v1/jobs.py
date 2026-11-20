from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select

from app.api.contracts import JobContract
from app.api.dependencies import Database, RequestKey, mutation_header
from app.auth import Actor, require_permissions
from app.domain import DomainError
from app.jobs import service
from app.jobs.models import artifacts, items, jobs
from app.jobs.reports import stream_report
from app.jobs.schemas import ItemPage, JobPage, JobReport, JobResponse, Submit
from app.sets.models import sets
from app.sets.service import visible

router = APIRouter(prefix="/admin/jobs", tags=["jobs"])
Reader = Annotated[Actor, Depends(require_permissions("jobs:read", "sets:read", "resources:read"))]


contract_router = APIRouter(prefix="/admin/contracts", tags=["contracts"])


@router.get("", response_model=JobPage, operation_id="jobs_list", summary="List jobs")
async def index(
    actor: Reader,
    database: Database,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
):
    if actor.kind != "user":
        raise DomainError(403, "permission_denied", "Permission denied")
    async with database.connect() as connection:
        connection = await connection.execution_options(isolation_level="REPEATABLE READ")
        async with connection.begin():
            query = select(jobs).join(sets).where(visible(actor))
            total = await connection.scalar(select(func.count()).select_from(query.subquery()))
            rows = (
                (
                    await connection.execute(
                        query.order_by(jobs.c.created_at.desc(), jobs.c.job_id)
                        .offset(offset)
                        .limit(limit)
                    )
                )
                .mappings()
                .all()
            )
            return {
                "items": [await service.response(connection, row) for row in rows],
                "total": total,
                "offset": offset,
                "limit": limit,
            }


@contract_router.get(
    "/jobs",
    response_model=JobContract,
    operation_id="jobs_get_contract",
    summary="Get Job editor contract",
)
async def contract(actor: Reader):
    return {
        "can_cancel": actor.kind == "user" and "jobs:cancel" in actor.permissions,
        "can_download": actor.kind == "user" and "jobs:artifacts:read" in actor.permissions,
    }


@router.post(
    "",
    status_code=202,
    responses={
        202: {
            "headers": {
                "Location": {"description": "Canonical read URL", "schema": {"type": "string"}}
            }
        }
    },
    response_model=JobResponse,
    dependencies=[Depends(mutation_header)],
    operation_id="jobs_submit_validation_job",
    summary="Create a Resource validation Job",
)
async def submit(
    response: Response,
    command: Submit,
    actor: Reader,
    database: Database,
    key: RequestKey,
    request: Request,
):
    """Validate inline versions or a saved selection; no publication certification."""
    result = await service.submit(
        database, actor, command, key, request.app.state.settings.app_version
    )
    response.headers["Location"] = f"/api/v1/admin/jobs/{result.job_id}"
    return result


@router.get("/{job_id}", response_model=JobResponse, operation_id="jobs_get", summary="Get a Job")
async def detail(job_id: UUID, actor: Reader, database: Database):
    async with database.connect() as connection:
        connection = await connection.execution_options(isolation_level="REPEATABLE READ")
        async with connection.begin():
            job = await service.readable(connection, actor, job_id)
            return await service.response(connection, job)


@router.get(
    "/{job_id}/items",
    response_model=ItemPage,
    operation_id="jobs_list_items",
    summary="List Job items",
)
async def results(
    job_id: UUID,
    actor: Reader,
    database: Database,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
):
    async with database.connect() as connection:
        await service.readable(connection, actor, job_id)
        rows = (
            (
                await connection.execute(
                    select(items)
                    .where(items.c.job_id == job_id)
                    .order_by(items.c.position)
                    .offset(offset)
                    .limit(limit)
                )
            )
            .mappings()
            .all()
        )
        total = await connection.scalar(
            select(func.count()).select_from(items).where(items.c.job_id == job_id)
        )
        return {"items": rows, "total": total, "offset": offset, "limit": limit}


@router.post(
    "/{job_id}/cancel",
    response_model=JobResponse,
    dependencies=[Depends(mutation_header)],
    operation_id="jobs_cancel",
    summary="Cancel a Job",
)
async def cancel(job_id: UUID, actor: Reader, database: Database):
    """Idempotently stop remaining items; retain already committed results."""
    return await service.cancel(database, actor, job_id)


@router.get(
    "/{job_id}/report",
    responses={
        200: {
            "model": JobReport,
            "description": "Immutable JSON report; streamed without buffering",
            "headers": {
                "Content-Disposition": {
                    "description": "Attachment filename",
                    "schema": {"type": "string"},
                }
            },
        }
    },
    operation_id="jobs_download_report",
    summary="Download Job report",
)
async def report(job_id: UUID, actor: Reader, database: Database):
    async with database.connect() as connection:
        await service.readable(connection, actor, job_id, {"jobs:artifacts:read"})
        artifact = (
            (
                await connection.execute(
                    select(
                        artifacts,
                        (artifacts.c.expires_at <= func.clock_timestamp()).label("expired"),
                    ).where(artifacts.c.job_id == job_id)
                )
            )
            .mappings()
            .first()
        )
        if artifact is None:
            raise DomainError(404, "not_found", "Report not ready")
        if artifact["expired"] or artifact["expired_at"] is not None:
            raise DomainError(410, "expired", "Report expired under retention policy")
        headers = {
            "Content-Disposition": f'attachment; filename="job-{job_id}.json"',
            "Cache-Control": "no-store",
            "ETag": '"' + artifact["checksum"] + '"',
            "X-Content-Type-Options": "nosniff",
            "Content-Length": str(artifact["byte_count"]),
        }
        if artifact["content"] is not None:
            return Response(
                bytes(artifact["content"]), media_type="application/json", headers=headers
            )
        return StreamingResponse(
            stream_report(database, actor, job_id, artifact["artifact_id"]),
            media_type="application/json",
            headers=headers,
        )
