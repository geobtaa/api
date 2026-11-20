from fastapi import APIRouter, Depends, Request, Response

from app.api.contracts import ErrorResponse, SignInResponse
from app.api.dependencies import Database, RequestKey, mutation_header
from app.api.v1.identity import Administrator
from app.auth import LOCAL_COOKIE
from app.identity import passwords
from app.identity.local_schemas import (
    CATALOG_EDITOR_PERMISSIONS,
    LocalAccount,
    LocalEmail,
    PasswordLogin,
    SetupResponse,
)

router = APIRouter(
    prefix="/admin/identity/local", tags=["identity"], dependencies=[Depends(mutation_header)]
)


@router.post("/accounts", response_model=SetupResponse, operation_id="identity_local_provision")
async def provision(
    command: LocalEmail,
    actor: Administrator,
    database: Database,
    key: RequestKey,
    response: Response,
):
    """Return a single-use setup code once. Replays return only account and expiry."""
    response.headers["Cache-Control"] = "no-store"
    tester = LocalAccount(
        email=command.email, permissions=sorted(CATALOG_EDITOR_PERMISSIONS), set_ids=None
    )
    return await passwords.provision(database, actor, tester, key)


@router.post("/resets", response_model=SetupResponse, operation_id="identity_local_reset")
async def reset(
    command: LocalEmail,
    actor: Administrator,
    database: Database,
    key: RequestKey,
    response: Response,
):
    """Revoke existing credentials and issue a replacement setup code."""
    response.headers["Cache-Control"] = "no-store"
    return await passwords.provision(database, actor, command, key, reset=True)


@router.post(
    "/sessions",
    response_model=SignInResponse,
    operation_id="identity_local_sign_in",
    responses={429: {"model": ErrorResponse}},
)
async def sign_in(command: PasswordLogin, request: Request, database: Database, response: Response):
    """Supply a setup code only when choosing the account password."""
    settings = request.app.state.settings
    token, expires = await passwords.login(
        database,
        command,
        request.client.host if request.client else "unknown",
        settings.auth_session_ttl_seconds or 28800,
    )
    response.set_cookie(
        LOCAL_COOKIE,
        token,
        secure=True,
        httponly=True,
        samesite="strict",
        path="/admin" if settings.app_env == "dev2" else "/",
        expires=expires,
    )
    response.headers["Cache-Control"] = "no-store"
    return {"authenticated": True, "expires_at": expires}
