from contextlib import asynccontextmanager
from uuid import uuid4

import httpx2
import pytest
from test_api import make_settings

from app.auth import Actor
from app.main import create_app

BASE = "/api/v1/admin/sets"


class UnavailableDatabase:
    @asynccontextmanager
    async def connect(self):
        raise OSError("private database connection details")
        yield  # pragma: no cover

    begin = connect


@pytest.mark.parametrize(
    "method,path,payload",
    [
        ("GET", BASE, None),
        ("GET", BASE + "/example", None),
        ("GET", BASE + "/example/activity", None),
        ("GET", BASE + "/example/state-preview?target=inactive", None),
        (
            "PUT",
            BASE + "/example/state",
            {"target": "inactive", "lock_version": 1, "reason": "Pause", "confirmed": True},
        ),
        ("POST", BASE, {"title": "Example", "source_id": "parent"}),
        ("PATCH", BASE + "/example", {"title": "Updated", "lock_version": 1}),
    ],
)
async def test_database_failure_has_recoverable_response(method, path, payload):
    async def authenticate(_):
        return Actor(
            "staff",
            "user",
            "Staff",
            None,
            frozenset(
                {
                    "sources:read",
                    "sources:use",
                    "sets:read",
                    "sets:create",
                    "sets:update",
                    "set-activity:read",
                }
            ),
        )

    app = create_app(authenticator=authenticate, settings=make_settings())
    app.state.database_engine = UnavailableDatabase()
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.request(
            method,
            path,
            json=payload,
            headers={"Idempotency-Key": str(uuid4()), "X-GEOMG-Request": "1"},
        )
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "database_unavailable"
    assert "private database" not in response.text


def test_openapi_has_independent_set_contract():
    document = create_app(settings=make_settings()).openapi()
    schemas = document["components"]["schemas"]
    create = schemas["SetCreate"]
    assert "lifecycle_id" not in create["properties"]
    assert create["required"] == ["title", "source_id"]
    assert "status" not in schemas["SetUpdate"]["properties"]
    assert create["properties"]["status"]["enum"] == ["active", "inactive"]
    assert "set_id" not in schemas["SetUpdate"]["properties"]
    assert "source_id" not in schemas["SetUpdate"]["properties"]
    assert schemas["SetUpdate"]["properties"]["lock_version"]["minimum"] == 1
    assert "admin_notes" in schemas["SetResponse"]["properties"]
    assert BASE in document["paths"] and "/api/v1/sets" not in document["paths"]


@pytest.mark.parametrize(
    "kind,permissions,status",
    [
        ("user", {"sets:read", "sources:read"}, 200),
        (
            "user",
            {
                "sources:read",
                "sources:use",
                "sets:read",
                "sets:create",
                "sets:update",
                "set-activity:read",
                "resources:read",
            },
            200,
        ),
        ("user", {"resources:read"}, 403),
        ("service_account", {"sets:read", "sets:update"}, 403),
    ],
)
async def test_set_form_contract_is_current_and_protected(kind, permissions, status):
    async def authenticate(_):
        return Actor("staff", kind, "Staff", None, frozenset(permissions))

    app = create_app(authenticator=authenticate, settings=make_settings())
    async with httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/admin/contracts/sets")
    assert response.status_code == status
    if status == 200:
        contract = response.json()
        for capability, permission in [
            ("create", "sets:create"),
            ("update", "sets:update"),
            ("activity_read", "set-activity:read"),
        ]:
            assert contract[capability] == (permission in permissions)
        assert contract["fields"]["title"]["maxLength"] == 250
        assert contract["fields"]["set_id"]["maxLength"] == 128
