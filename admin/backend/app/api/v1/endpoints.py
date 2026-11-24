import logging

from fastapi import APIRouter, Request

from app.api.v1.schemas import HealthResponse, ReadyResponse
from app.domain import DomainError

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    tags=["system"],
    operation_id="system_health",
    summary="Check liveness",
)
async def health(request: Request) -> HealthResponse:
    """Report process liveness without contacting dependencies."""
    return HealthResponse(
        status="ok",
        service=request.app.state.settings.app_name,
        version=request.app.state.settings.app_version,
    )


@router.get(
    "/ready",
    response_model=ReadyResponse,
    tags=["system"],
    operation_id="system_ready",
    summary="Check database readiness",
)
async def ready(request: Request) -> ReadyResponse:
    """Report whether the API can reach its authoritative database."""
    try:
        await request.app.state.readiness_check()
    except Exception as exc:
        logger.warning("Readiness check failed: %s", exc)
        raise DomainError(503, "database_unavailable", "Database unavailable") from exc

    return ReadyResponse(status="ready", database="available")
