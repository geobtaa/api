from dataclasses import replace
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import httpx2
import pytest
from sqlalchemy import func, select, update
from test_api import make_settings
from test_managing_sets import EDITOR, create, headers
from test_managing_sets import api as managing_set_api

from app.auth import build_authenticator
from app.domain import DomainError
from app.identity import service
from app.identity.models import accounts, audit, invitations, sessions
from app.identity.schemas import AccountChange, Invitation
from app.main import create_app
from app.persistence import actors

api = managing_set_api
pytestmark = pytest.mark.integration
BASE = "/api/v1/admin/identity"
PERMISSIONS = EDITOR.permissions | {"identity:manage", "jobs:read", "jobs:submit", "resources:read"}
ADMIN = replace(EDITOR, permissions=PERMISSIONS)
IDENTITY = service.VerifiedIdentity(
    next(iter(service.ALLOWED_IDPS)), "subject-1@example.edu", "Steward", "urn:test:mfa"
)
CONTEXTS = ("urn:test:mfa",)


def command(**extra):
    return Invitation(
        idp_entity_id=IDENTITY.idp_entity_id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=1),
        permissions=["sets:read", "sources:read", "resources:read", "jobs:read", "jobs:submit"],
        **extra,
    )


async def issue(engine, invitation=None):
    return await service.create_invitation(engine, ADMIN, invitation or command(), uuid4())


async def test_invitation_first_stable_identity_sessions_and_current_grants(database_engine):
    with pytest.raises(DomainError, match="Institutional sign-in unavailable"):
        await service.establish_session(database_engine, IDENTITY, None, 3600, CONTEXTS)
    invitation = await issue(database_engine)
    token, expires = await service.establish_session(
        database_engine, IDENTITY, invitation["token"], 3600, CONTEXTS
    )
    assert expires > datetime.now(timezone.utc)
    actor = await service.authenticate_session(database_engine, token, CONTEXTS)
    assert actor.actor_id == service.identity_key(IDENTITY)
    assert actor.set_ids == frozenset()
    assert "identity:manage" not in actor.permissions
    assert await service.authenticate_session(database_engine, token, ()) is None
    async with database_engine.connect() as connection:
        subject = (
            (await connection.execute(select(actors).where(actors.c.subject_key == actor.actor_id)))
            .mappings()
            .one()
        )
        assert (await service.resolve_actor(connection, subject)) == actor
        stored = (await connection.execute(select(sessions))).mappings().one()
        assert stored["token_hash"] == service.token_hash(token) and token not in str(stored)
    # Same institutional identity needs no second invitation; different IdP never auto-links.
    second, _ = await service.establish_session(
        database_engine, replace(IDENTITY, display_name="Changed"), None, 3600, CONTEXTS
    )
    with pytest.raises(DomainError):
        await service.establish_session(
            database_engine,
            replace(IDENTITY, subject_id="another"),
            invitation["token"],
            3600,
            CONTEXTS,
        )
    change = AccountChange(active=True, permissions=["sets:read"], set_ids=None, lock_version=1)
    result = await service.change_account(database_engine, ADMIN, subject["id"], change, uuid4())
    assert result["lock_version"] == 2
    current = await service.authenticate_session(database_engine, token, CONTEXTS)
    assert current.permissions == {"sets:read"} and current.set_ids is None
    with pytest.raises(DomainError, match="Account grants changed"):
        await service.change_account(database_engine, ADMIN, subject["id"], change, uuid4())
    await service.change_account(
        database_engine,
        ADMIN,
        subject["id"],
        change.model_copy(update={"active": False, "lock_version": 2}),
        uuid4(),
    )
    assert await service.authenticate_session(database_engine, second, CONTEXTS) is None
    with pytest.raises(DomainError):
        await service.establish_session(database_engine, IDENTITY, None, 3600, CONTEXTS)
    async with database_engine.connect() as connection:
        assert await connection.scalar(select(func.count()).select_from(audit)) >= 7
        assert (
            await connection.scalar(
                select(accounts.c.active).where(accounts.c.actor_id == subject["id"])
            )
            is False
        )


async def test_invitation_contract_expiration_revocation_and_scope(api, database_engine):
    client, actor = api
    actor[0] = ADMIN
    managing_set = await create(client)
    spec = command(set_ids=[managing_set["set_id"]])
    key = uuid4()
    first = await client.post(
        BASE + "/invitations", headers=headers(key), json=spec.model_dump(mode="json")
    )
    assert first.status_code == 201, first.text
    assert first.headers["cache-control"] == "no-store"
    assert len(first.json()["token"]) >= 40
    replay = await client.post(
        BASE + "/invitations", headers=headers(key), json=spec.model_dump(mode="json")
    )
    assert replay.json()["token"] is None
    changed = spec.model_copy(update={"permissions": ["sets:read"]})
    assert (
        await client.post(
            BASE + "/invitations", headers=headers(key), json=changed.model_dump(mode="json")
        )
    ).status_code == 409
    revoked = BASE + "/invitations/" + first.json()["invitation_id"] + "/revoke"
    assert (await client.post(revoked, headers=headers())).status_code == 200
    assert (await client.post(revoked, headers=headers())).status_code == 200
    with pytest.raises(DomainError):
        await service.establish_session(
            database_engine, IDENTITY, first.json()["token"], 3600, CONTEXTS
        )
    assert (
        await client.post(BASE + f"/invitations/{uuid4()}/revoke", headers=headers())
    ).status_code == 404
    for invalid, status in [
        (spec.model_copy(update={"idp_entity_id": "unknown"}), 422),
        (spec.model_copy(update={"permissions": ["unauthorized:permission"]}), 403),
        (
            spec.model_copy(
                update={"expires_at": datetime.now(timezone.utc) - timedelta(seconds=1)}
            ),
            422,
        ),
        (spec.model_copy(update={"set_ids": [str(uuid4())]}), 404),
    ]:
        assert (
            await client.post(
                BASE + "/invitations", headers=headers(), json=invalid.model_dump(mode="json")
            )
        ).status_code == status
    token = (await issue(database_engine, spec))["token"]
    session, _ = await service.establish_session(database_engine, IDENTITY, token, 3600, CONTEXTS)
    assert (await service.authenticate_session(database_engine, session, CONTEXTS)).set_ids == {
        managing_set["set_id"]
    }
    await service.revoke_session(database_engine, session)
    await service.revoke_session(database_engine, session)
    assert await service.authenticate_session(database_engine, session, CONTEXTS) is None
    assert await service.authenticate_session(database_engine, "x" * 300, CONTEXTS) is None
    actor[0] = replace(ADMIN, set_ids=frozenset())
    assert (
        await client.post(
            BASE + "/invitations", headers=headers(), json=spec.model_dump(mode="json")
        )
    ).status_code == 403


async def test_http_boundary_ignores_headers_sets_secure_cookie_and_logs_out(database_engine):
    settings = replace(
        make_settings(), auth_session_ttl_seconds=3600, auth_accepted_contexts=CONTEXTS
    )
    app = create_app(settings=settings)
    app.state.database_engine = database_engine
    verified = [None]

    async def verifier(request):
        return verified[0]

    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=app), base_url="https://test"
    ) as client:
        assert len((await client.get(BASE + "/providers")).json()["items"]) == 18
        assert (
            await client.post("/api/v1/admin/session", headers=headers(), json={})
        ).status_code == 503
        app.state.federation_verifier = verifier
        response = await client.post(
            "/api/v1/admin/session",
            headers={
                **headers(),
                "Shib-Identity-Provider": IDENTITY.idp_entity_id,
                "subject-id": IDENTITY.subject_id,
            },
            json={},
        )
        assert response.status_code == 401
        invitation = await issue(database_engine)
        verified[0] = IDENTITY
        response = await client.post(
            "/api/v1/admin/session",
            headers=headers(),
            json={"invitation_token": invitation["token"]},
        )
        assert response.status_code == 200, response.text
        assert "token" not in response.json()
        cookie = response.headers["set-cookie"]
        assert "Secure" in cookie and "HttpOnly" in cookie and "SameSite=lax" in cookie
        # Authenticator is exercised through an existing protected endpoint.
        assert (await client.get("/api/v1/admin/sets")).status_code == 200
        assert (await client.delete("/api/v1/admin/session", headers=headers())).status_code == 200
        assert (await client.get("/api/v1/admin/sets")).status_code == 401
    assert callable(build_authenticator(settings))


async def test_invalid_assurance_subject_and_expired_session(database_engine):
    for identity in [
        None,
        replace(IDENTITY, idp_entity_id="unknown"),
        replace(IDENTITY, subject_id=""),
        replace(IDENTITY, authentication_context="weak"),
    ]:
        with pytest.raises(DomainError):
            await service.establish_session(database_engine, identity, None, 3600, CONTEXTS)
    token = (await issue(database_engine))["token"]
    session, _ = await service.establish_session(database_engine, IDENTITY, token, 3600, CONTEXTS)
    async with database_engine.begin() as connection:
        await connection.execute(update(sessions).values(expires_at=func.clock_timestamp()))
        row = (await connection.execute(select(invitations))).mappings().one()
        assert row["token_hash"] != token
    assert await service.authenticate_session(database_engine, session, CONTEXTS) is None


async def test_account_api_replays_changes_and_enforces_delegation(api, database_engine):
    client, actor = api
    actor[0] = ADMIN
    invitation = await issue(database_engine)
    await service.establish_session(database_engine, IDENTITY, invitation["token"], 3600, CONTEXTS)
    async with database_engine.connect() as connection:
        target = await connection.scalar(select(accounts.c.actor_id))
    path = BASE + f"/accounts/{target}"
    current = (await client.get(path)).json()
    assert current["lock_version"] == 1 and current["set_ids"] == []
    payload = {
        "lock_version": 1,
        "active": True,
        "permissions": ["sets:read"],
        "set_ids": [],
    }
    key = uuid4()
    first = await client.put(path, headers=headers(key), json=payload)
    assert first.status_code == 200
    assert (await client.put(path, headers=headers(key), json=payload)).json() == first.json()
    assert (
        await client.put(path, headers=headers(key), json={**payload, "active": False})
    ).status_code == 409
    assert (await client.get(BASE + f"/accounts/{uuid4()}")).status_code == 404
    assert (
        await client.put(BASE + f"/accounts/{uuid4()}", headers=headers(), json=payload)
    ).status_code == 404
    for invalid in [{**payload, "permissions": ["bad"]}, {**payload, "lock_version": 0}]:
        assert (await client.put(path, headers=headers(), json=invalid)).status_code == 422
    invalid = command().model_dump(mode="json")
    invalid["expires_at"] = "2026-12-04T00:00:00"
    assert (
        await client.post(BASE + "/invitations", headers=headers(), json=invalid)
    ).status_code == 422
    actor[0] = EDITOR
    assert (await client.get(path)).status_code == 403
