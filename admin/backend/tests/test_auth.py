from pathlib import Path

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from app.auth import SESSION_READ_PERMISSION, Actor
from app.config import Settings
from app.main import create_app


def make_settings(**overrides) -> Settings:
    values = {
        "app_env": "test",
        "app_name": "GEOMG Admin",
        "app_version": "0.1.0-test",
        "cors_origins": ("http://localhost:3000",),
        "database_url": "postgresql+asyncpg://unused:unused@localhost/unused",
    }
    values.update(overrides)
    return Settings(**values)


def test_protected_session_fails_closed_without_an_authenticator(tmp_path: Path) -> None:
    application = create_app(frontend_dist=tmp_path, settings=make_settings())

    with TestClient(application) as client:
        response = client.get("/api/v1/admin/session")

    assert response.status_code == 401
    assert response.json() == {
        "detail": {"code": "unauthenticated", "message": "Authentication required", "errors": []}
    }


def test_protected_session_returns_the_current_actor(tmp_path: Path) -> None:
    async def authenticate(_: Request) -> Actor:
        return Actor(
            actor_id="actor-123",
            kind="user",
            display_name="Metadata Steward",
            email="steward@example.org",
            permissions=frozenset({SESSION_READ_PERMISSION, "resources:read"}),
            lifecycle_ids=frozenset({"lifecycle-2", "lifecycle-1"}),
        )

    application = create_app(
        authenticator=authenticate,
        frontend_dist=tmp_path,
        settings=make_settings(),
    )

    with TestClient(application) as client:
        response = client.get("/api/v1/admin/session")

    assert response.status_code == 200
    assert response.json() == {
        "authenticated": True,
        "actor": {
            "actor_id": "actor-123",
            "kind": "user",
            "display_name": "Metadata Steward",
            "email": "steward@example.org",
            "permissions": ["admin.session:read", "resources:read"],
            "set_ids": None,
        },
    }


def test_protected_session_requires_its_permission(tmp_path: Path) -> None:
    async def authenticate(_: Request) -> Actor:
        return Actor(
            actor_id="actor-123",
            kind="user",
            display_name="Read-only actor",
            email=None,
            permissions=frozenset(),
        )

    application = create_app(
        authenticator=authenticate,
        frontend_dist=tmp_path,
        settings=make_settings(),
    )

    with TestClient(application) as client:
        response = client.get("/api/v1/admin/session")

    assert response.status_code == 403
    assert response.json() == {
        "detail": {"code": "permission_denied", "message": "Permission denied", "errors": []}
    }


def test_development_identity_is_available_only_in_safe_environments(tmp_path: Path) -> None:
    settings = make_settings(
        auth_mode="development",
        dev_auth_actor_id="local-developer",
        dev_auth_display_name="Local Developer",
        dev_auth_email="developer@localhost",
        dev_auth_permissions=(SESSION_READ_PERMISSION,),
    )
    application = create_app(frontend_dist=tmp_path, settings=settings)

    with TestClient(application) as client:
        response = client.get("/api/v1/admin/session")

    assert response.status_code == 200
    assert response.json()["actor"]["actor_id"] == "local-developer"

    with pytest.raises(ValueError, match="forbidden"):
        make_settings(
            app_env="production",
            auth_mode="development",
            dev_auth_actor_id="unsafe",
            dev_auth_display_name="Unsafe Developer",
        )
