from dataclasses import replace
from datetime import timedelta
from uuid import uuid4

import httpx2
import pytest
from sqlalchemy import func, select, update
from test_api import make_settings

from app.domain import DomainError
from app.identity import passwords
from app.identity.local_schemas import LocalAccount
from app.identity.models import local_credentials
from app.main import create_app

ROOT = "/api/v1/admin"
LOCAL = ROOT + "/identity/local"
H = {"X-GEOMG-Request": "1"}
PASSWORD = "a long test password for the alpha"


def test_local_mode_is_explicit():
    with pytest.raises(ValueError, match="Local passwords"):
        replace(make_settings(), auth_mode="local-password", app_env="production")
    assert LOCAL + "/sessions" not in create_app(settings=make_settings()).openapi()["paths"]


@pytest.mark.integration
async def test_alpha_accounts(database_engine):
    settings = replace(make_settings(), auth_mode="local-password", app_env="dev2")
    app = create_app(settings=settings)
    app.state.database_engine = database_engine
    transport = httpx2.ASGITransport(app=app, root_path="/admin")
    base = "https://testserver/admin"
    admin = LocalAccount(
        email="Owner@Example.edu", permissions=["identity:manage", "resources:read"], set_ids=None
    )
    initial = await passwords.provision(database_engine, None, admin, uuid4(), bootstrap=True)
    with pytest.raises(DomainError):
        await passwords.provision(database_engine, None, admin, uuid4(), bootstrap=True)
    async with (
        httpx2.AsyncClient(transport=transport, base_url=base) as owner,
        httpx2.AsyncClient(transport=transport, base_url=base) as tester,
    ):

        async def signin(client, email, code=None):
            return await client.post(
                LOCAL + "/sessions",
                headers=H,
                json={
                    "email": email,
                    "password": PASSWORD,
                    **({"setup_code": code} if code else {}),
                },
            )

        signed = await signin(owner, admin.email, initial["setup_code"])
        assert signed.status_code == 200, signed.text
        assert all(
            part in signed.headers["set-cookie"]
            for part in ["Secure", "HttpOnly", "Path=/admin", "SameSite=strict"]
        )
        who = await owner.get(ROOT + "/session")
        assert who.status_code == 200, who.text
        key = {**H, "Idempotency-Key": str(uuid4())}
        data = {"email": "tester@example.edu", "permissions": ["resources:read"], "set_ids": []}
        assert (await tester.post(LOCAL + "/accounts", headers=key, json=data)).status_code == 401
        created = await owner.post(LOCAL + "/accounts", headers=key, json=data)
        assert created.status_code == 200, created.text
        assert created.headers["cache-control"] == "no-store"
        code = created.json()["setup_code"]
        assert (await owner.post(LOCAL + "/accounts", headers=key, json=data)).json()[
            "setup_code"
        ] is None
        assert (await signin(tester, data["email"], code)).status_code == 200
        assert (await signin(tester, data["email"], code)).status_code == 401
        assert (await tester.get(ROOT + "/session")).json()["actor"]["set_ids"] == []
        assert (await tester.post(LOCAL + "/accounts", headers=key, json=data)).status_code == 403
        assert (await tester.get(ROOT + "/resources")).json()["items"] == []
        assert (await tester.delete(ROOT + "/session", headers=H)).status_code == 200
        assert (await tester.get(ROOT + "/session")).status_code == 401
        assert (await signin(tester, data["email"])).status_code == 200
        reset = await owner.post(
            LOCAL + "/resets",
            headers={**H, "Idempotency-Key": str(uuid4())},
            json={"email": data["email"]},
        )
        assert reset.status_code == 200, reset.text
        assert (await tester.get(ROOT + "/session")).status_code == 401
        assert (await signin(tester, data["email"])).status_code == 401
        async with database_engine.begin() as conn:
            await conn.execute(
                update(local_credentials)
                .where(local_credentials.c.email == data["email"])
                .values(setup_expires_at=func.now() - timedelta(seconds=1))
            )
            encoded = await conn.scalar(
                select(local_credentials.c.password_hash).where(
                    local_credentials.c.email == admin.email
                )
            )
            assert encoded.startswith("$argon2id$")
        assert (await signin(tester, data["email"], reset.json()["setup_code"])).status_code == 401
        target = ROOT + "/identity/accounts/" + created.json()["actor_id"]
        assert (
            await owner.put(
                target,
                headers={**H, "Idempotency-Key": str(uuid4())},
                json={"active": False, "permissions": [], "set_ids": [], "lock_version": 1},
            )
        ).status_code == 200
        assert (await signin(tester, data["email"])).status_code == 401
        unknown = await signin(tester, "outsider@example.edu")
        assert unknown.json() == (await signin(tester, data["email"])).json()
        for _ in range(10):
            limited = await signin(tester, "outsider@example.edu")
        assert limited.status_code == 429
