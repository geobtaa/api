from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyCookie

from app.config import Settings

LOCAL_COOKIE = "__Secure-geomg-alpha-session"

session_cookie = APIKeyCookie(
    name="__Host-geomg-session",
    scheme_name="SessionCookie",
    auto_error=False,
    description=(
        "Institutional HttpOnly session cookie. Local development may use a configured "
        "development actor. No bearer or machine token transport is implemented."
    ),
)


ActorKind = Literal["user", "service_account", "system"]
SESSION_READ_PERMISSION = "admin.session:read"


@dataclass(frozen=True)
class Actor:
    actor_id: str
    kind: ActorKind
    display_name: str
    email: str | None
    permissions: frozenset[str]
    lifecycle_ids: frozenset[str] | None = None
    # None is the existing global Set grant; a collection narrows it explicitly.
    set_ids: frozenset[str] | None = None


Authenticator = Callable[[Request], Awaitable[Actor | None]]


def build_authenticator(settings: Settings) -> Authenticator:
    if settings.auth_mode == "development":
        actor = Actor(
            actor_id=settings.dev_auth_actor_id or "",
            kind="user",
            display_name=settings.dev_auth_display_name or "",
            email=settings.dev_auth_email,
            permissions=frozenset(settings.dev_auth_permissions),
        )

        async def authenticate_development(_: Request) -> Actor:
            return actor

        return authenticate_development

    async def authenticate_institutional(request: Request) -> Actor | None:
        from app.identity.service import COOKIE, authenticate_session

        local = settings.auth_mode == "local-password"
        contexts = ("local-password",) if local else settings.auth_accepted_contexts
        if not local and (not settings.auth_session_ttl_seconds or not contexts):
            return None
        token = request.cookies.get(LOCAL_COOKIE if local else COOKIE)
        if not token:
            return None
        from app.api.dependencies import engine

        return await authenticate_session(engine(request), token, contexts)

    return authenticate_institutional


async def get_current_actor(
    request: Request, _session: str | None = Depends(session_cookie)
) -> Actor:
    actor = await request.app.state.authenticator(request)
    if actor is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"X-GEOMG-Auth-Mode": request.app.state.settings.auth_mode},
        )
    return actor


def require_permissions(*required_permissions: str) -> Callable[[Request], Awaitable[Actor]]:
    required = frozenset(required_permissions)

    async def authorize(request: Request, _session: str | None = Depends(session_cookie)) -> Actor:
        actor = await get_current_actor(request)
        if not required.issubset(actor.permissions):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission denied",
            )
        return actor

    return authorize
