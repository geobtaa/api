from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel

from app.auth import SESSION_READ_PERMISSION, Actor, require_permissions

router = APIRouter(prefix="/admin", tags=["session"])


class SessionActorResponse(BaseModel):
    actor_id: str
    kind: Literal["user", "service_account", "system"]
    display_name: str
    email: str | None
    permissions: list[str]
    set_ids: list[str] | None


class SessionResponse(BaseModel):
    authenticated: Literal[True]
    actor: SessionActorResponse


@router.get(
    "/session",
    response_model=SessionResponse,
    operation_id="session_session",
    summary="Get current session",
)
async def session(
    request: Request,
    response: Response,
    actor: Annotated[Actor, Depends(require_permissions(SESSION_READ_PERMISSION))],
) -> SessionResponse:
    """Return the non-secret identity and grants for the current session."""
    response.headers["X-GEOMG-Auth-Mode"] = request.app.state.settings.auth_mode
    response.headers["Cache-Control"] = "no-store"
    return SessionResponse(
        authenticated=True,
        actor=SessionActorResponse(
            actor_id=actor.actor_id,
            kind=actor.kind,
            display_name=actor.display_name,
            email=actor.email,
            permissions=sorted(actor.permissions),
            set_ids=sorted(actor.set_ids) if actor.set_ids is not None else None,
        ),
    )
