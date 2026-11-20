from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response

from app.api.contracts import (
    AccountResponse,
    AccountUpdateResponse,
    InvitationResponse,
    ProvidersResponse,
    RevocationResponse,
    SignInResponse,
    SignOutResponse,
)
from app.api.dependencies import Database, RequestKey, mutation_header
from app.auth import LOCAL_COOKIE, Actor, require_permissions
from app.domain import DomainError
from app.identity import service
from app.identity.schemas import AccountChange, Invitation, SignIn

router = APIRouter(prefix="/admin/identity", tags=["identity"])
session_router = APIRouter(prefix="/admin/session", tags=["session"])
Administrator = Annotated[Actor, Depends(require_permissions("identity:manage"))]


@router.get(
    "/providers",
    response_model=ProvidersResponse,
    operation_id="identity_providers",
    summary="List institutional identity providers",
)
async def providers():
    """Reviewed DEC-008 institution picker; no unrestricted federation discovery."""
    return {"items": service.PROVIDERS}


@router.post(
    "/invitations",
    response_model=InvitationResponse,
    status_code=201,
    dependencies=[Depends(mutation_header)],
    operation_id="identity_invite",
    summary="Create an invitation",
)
async def invite(
    command: Invitation,
    actor: Administrator,
    database: Database,
    key: RequestKey,
    response: Response,
):
    """Return the token once; replay returns metadata. Revoke and replace a lost token."""
    response.headers["Cache-Control"] = "no-store"
    return await service.create_invitation(database, actor, command, key)


@router.post(
    "/invitations/{invitation_id}/revoke",
    response_model=RevocationResponse,
    dependencies=[Depends(mutation_header)],
    operation_id="identity_revoke_invitation",
    summary="Revoke invitation",
)
async def revoke_invitation(invitation_id: UUID, actor: Administrator, database: Database):
    await service.revoke_invitation(database, actor, invitation_id)
    return {"revoked": True}


@router.get(
    "/accounts/{actor_id}",
    response_model=AccountResponse,
    operation_id="identity_account_detail",
    summary="Get an account",
)
async def account_detail(actor_id: UUID, actor: Administrator, database: Database):
    return await service.account_detail(database, actor, actor_id)


@router.put(
    "/accounts/{actor_id}",
    response_model=AccountUpdateResponse,
    dependencies=[Depends(mutation_header)],
    operation_id="identity_change_account",
    summary="Replace account grants",
)
async def change_account(
    actor_id: UUID,
    command: AccountChange,
    actor: Administrator,
    database: Database,
    key: RequestKey,
):
    """Replace explicit grants using the last read optimistic account version."""
    return await service.change_account(database, actor, actor_id, command, key)


@session_router.post(
    "",
    response_model=SignInResponse,
    dependencies=[Depends(mutation_header)],
    operation_id="identity_sign_in",
    summary="Establish current session",
)
async def sign_in(command: SignIn, request: Request, database: Database, response: Response):
    """Consume server-verified federation evidence. Never accept raw browser identity headers."""
    verifier = request.app.state.federation_verifier
    settings = request.app.state.settings
    if (
        settings.auth_mode == "local-password"
        or verifier is None
        or not settings.auth_session_ttl_seconds
        or not settings.auth_accepted_contexts
    ):
        raise DomainError(503, "federation_unconfigured", "Institutional sign-in is not configured")
    identity = await verifier(request)
    token, expires = await service.establish_session(
        database,
        identity,
        command.invitation_token,
        settings.auth_session_ttl_seconds,
        settings.auth_accepted_contexts,
    )
    response.set_cookie(
        service.COOKIE, token, secure=True, httponly=True, samesite="lax", path="/", expires=expires
    )
    response.headers["Cache-Control"] = "no-store"
    return {"authenticated": True, "expires_at": expires}


@session_router.delete(
    "",
    response_model=SignOutResponse,
    dependencies=[Depends(mutation_header)],
    operation_id="identity_logout",
    summary="End current session",
)
async def logout(request: Request, database: Database, response: Response):
    settings = request.app.state.settings
    local = settings.auth_mode == "local-password"
    cookie = LOCAL_COOKIE if local else service.COOKIE
    path = "/admin" if local and settings.app_env == "dev2" else "/"
    await service.revoke_session(database, request.cookies.get(cookie))
    response.delete_cookie(cookie, path=path, secure=True, httponly=True, samesite="lax")
    response.headers["Cache-Control"] = "no-store"
    return {"authenticated": False}
