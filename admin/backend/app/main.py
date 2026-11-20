import os
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException

from app import catalog_csv
from app.api.contracts import ErrorResponse
from app.api.docs import swagger_docs
from app.api.errors import error_response, http_error, validation_error
from app.api.v1.admin import router as admin_router
from app.api.v1.bulk_actions import router as bulk_router
from app.api.v1.catalog_csv import routes as catalog_csv_routes
from app.api.v1.endpoints import router as v1_router
from app.api.v1.identity import router as identity_router
from app.api.v1.identity import session_router
from app.api.v1.jobs import contract_router as jobs_contract_router
from app.api.v1.jobs import router as jobs_router
from app.api.v1.resources import contract_router as resources_contract_router
from app.api.v1.resources import local_router as local_resource_router
from app.api.v1.resources import router as resource_router
from app.api.v1.sets import contract_router as sets_contract_router
from app.api.v1.sets import router as set_router
from app.api.v1.sources import contract_router as sources_contract_router
from app.api.v1.sources import router as source_router
from app.api.v1.work import contract_router as work_contract_router
from app.api.v1.work import maintenance_router, period_router
from app.api.v1.work import router as work_router
from app.api.v1.workflow_catalog import router as workflow_catalog_router
from app.api.v1.workflows import contract_router as workflows_contract_router
from app.api.v1.workflows import router as workflow_router
from app.auth import Authenticator, build_authenticator
from app.config import Settings, get_settings
from app.database import check_database, dispose_database
from app.domain import DomainError
from app.fixtures import router as fixture_router
from app.identity.service import VerifiedIdentity

ReadinessCheck = Callable[[], Awaitable[None]]


def create_app(
    *,
    readiness_check: ReadinessCheck = check_database,
    authenticator: Authenticator | None = None,
    federation_verifier: Callable[[Request], Awaitable[VerifiedIdentity | None]] | None = None,
    frontend_dist: Path | None = None,
    settings: Settings | None = None,
) -> FastAPI:
    app_settings = settings or get_settings()
    configured_frontend_dist = os.getenv("FRONTEND_DIST")
    static_root = (
        frontend_dist
        if frontend_dist is not None
        else Path(configured_frontend_dist)
        if configured_frontend_dist
        else Path(__file__).resolve().parents[2] / "frontend" / "dist"
    ).resolve()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        if hasattr(application.state, "database_engine"):
            await application.state.database_engine.dispose()
        await dispose_database()

    application = FastAPI(
        title=f"{app_settings.app_name} API",
        version=app_settings.app_version,
        description=(
            "Resourceful staff administration API. Resource URL keys preserve metadata IDs: "
            "ordinary IDs are literal; reserved or unsafe IDs use ~ plus unpadded base64url "
            "of the exact UTF-8 ID. See the Resource path parameter for the contract. "
            "Mutations require X-GEOMG-Request: 1 and, where declared, an Idempotency-Key. "
            "Institutional sessions are server-owned; local development may use a configured "
            "development actor. Federation deployment and machine authentication remain gated."
        ),
        openapi_tags=[
            {
                "name": "resources",
                "description": "Scoped canonical Resource metadata, imports and associations.",
            },
            {
                "name": "sources",
                "description": "Independent staff Source administration with global grants.",
            },
            {
                "name": "sets",
                "description": "Managing Resource scope, acquisition context, state and work.",
            },
            {
                "name": "workflows",
                "description": "Versioned definitions; activation does not execute work.",
            },
            {
                "name": "tasks",
                "description": "Staff work occurrences, maintenance and completion reporting.",
            },
            {
                "name": "work-periods",
                "description": "Named date ranges for accomplishment reports.",
            },
            {"name": "jobs", "description": "Durable draft-validation jobs and protected reports."},
            {
                "name": "contracts",
                "description": "Form constraints and actor capabilities; writes reauthorize.",
            },
            {
                "name": "session",
                "description": "Read, establish or revoke the current institutional session.",
            },
            {
                "name": "identity",
                "description": "Invitation-first accounts and grants for identity administrators.",
            },
            {"name": "system", "description": "Liveness and database readiness."},
            *(
                [
                    {
                        "name": "development fixtures",
                        "description": "Local-only fixture reads and Bridge staging.",
                    }
                ]
                if app_settings.app_env in {"development", "test"}
                else []
            ),
        ],
        docs_url=None,
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
        responses={
            status: {"model": ErrorResponse, "description": description}
            for status, description in {
                401: "Authentication required",
                403: "Permission denied",
                404: "Missing or inaccessible record",
                405: "Method not allowed",
                409: "Version, state, dependency or idempotency conflict",
                410: "Artifact expired",
                422: "Request validation failed",
                500: "Unexpected server failure; no internal details are returned",
                503: "Unavailable: retry reads; reuse the idempotency key for uncertain writes",
            }.items()
        },
    )
    application.add_api_route("/api/docs", swagger_docs, include_in_schema=False)
    application.state.readiness_check = readiness_check
    application.state.settings = app_settings
    application.state.authenticator = authenticator or build_authenticator(app_settings)
    application.state.federation_verifier = federation_verifier
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(app_settings.cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(v1_router, prefix="/api/v1")
    application.include_router(resources_contract_router, prefix="/api/v1")
    application.include_router(workflows_contract_router, prefix="/api/v1")
    application.include_router(jobs_contract_router, prefix="/api/v1")
    application.include_router(sources_contract_router, prefix="/api/v1")
    application.include_router(sets_contract_router, prefix="/api/v1")
    application.include_router(bulk_router, prefix="/api/v1")
    application.include_router(admin_router, prefix="/api/v1")
    if app_settings.app_env in {"development", "test"}:
        application.include_router(fixture_router, prefix="/api/v1")
        application.include_router(local_resource_router, prefix="/api/v1")
    if app_settings.app_env == "dev2":
        from app.resources.alpha_bridge import router as alpha_bridge_router

        application.include_router(alpha_bridge_router, prefix="/api/v1")
    application.include_router(resource_router, prefix="/api/v1")
    application.include_router(workflow_router, prefix="/api/v1")
    application.include_router(workflow_catalog_router, prefix="/api/v1")
    application.include_router(jobs_router, prefix="/api/v1")
    application.include_router(identity_router, prefix="/api/v1")
    application.include_router(session_router, prefix="/api/v1")
    if app_settings.auth_mode == "local-password":
        from app.api.v1.local_password import router as local_password_router

        application.include_router(local_password_router, prefix="/api/v1")
    for catalog in (catalog_csv.SOURCES, catalog_csv.SETS):
        application.include_router(catalog_csv_routes(catalog), prefix="/api/v1")
    application.include_router(source_router, prefix="/api/v1")
    application.include_router(set_router, prefix="/api/v1")
    application.include_router(work_router, prefix="/api/v1")
    application.include_router(maintenance_router, prefix="/api/v1")
    application.include_router(period_router, prefix="/api/v1")
    application.include_router(work_contract_router, prefix="/api/v1")

    application.add_exception_handler(HTTPException, http_error)
    application.add_exception_handler(RequestValidationError, validation_error)

    @application.exception_handler(Exception)
    async def unexpected_error(_, exc: Exception):
        return error_response(500, "internal_error", "The request could not be completed")

    @application.exception_handler(DomainError)
    async def domain_error(_, exc: DomainError):
        return error_response(exc.status, exc.code, exc.message)

    @application.exception_handler(OSError)
    @application.exception_handler(SQLAlchemyError)
    async def database_error(_, exc: SQLAlchemyError):
        return JSONResponse(
            status_code=503,
            content={
                "detail": {
                    "code": "database_unavailable",
                    "errors": [],
                    "message": (
                        "The database is unavailable. The result could not be confirmed; "
                        "retry the same request."
                    ),
                }
            },
        )

    @application.get("/{path:path}", include_in_schema=False, response_model=None)
    async def frontend(path: str) -> Response:
        if path == "api" or path.startswith("api/"):
            return error_response(404, "not_found", "Not found")
        candidate = (static_root / path).resolve()
        if path and candidate.is_relative_to(static_root) and candidate.is_file():
            return FileResponse(candidate)

        index = static_root / "index.html"
        if index.is_file():
            return FileResponse(index)

        return JSONResponse(
            {
                "name": app_settings.app_name,
                "version": app_settings.app_version,
                "docs": "/api/docs",
            }
        )

    if app_settings.auth_mode == "local-password":
        from app.auth import LOCAL_COOKIE

        original_openapi = application.openapi

        def local_openapi():
            spec = original_openapi()
            scheme = spec["components"]["securitySchemes"]["SessionCookie"]
            scheme.update(name=LOCAL_COOKIE, description="GEOMG alpha HttpOnly session cookie.")
            return spec

        application.openapi = local_openapi
    return application


app = create_app()
