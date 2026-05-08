from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.middleware.turnstile_middleware import TurnstileMiddleware
from app.services.turnstile_service import TurnstileService


def _make_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(TurnstileMiddleware)

    @app.get("/api/v1/search")
    async def search():
        return {"ok": True}

    @app.get("/api/v1/resources/example")
    async def resource():
        return {"ok": True}

    return app


def test_turnstile_middleware_allows_requests_when_disabled(monkeypatch):
    monkeypatch.setenv("TURNSTILE_ENABLED", "false")

    client = TestClient(_make_app())
    response = client.get("/api/v1/search")

    assert response.status_code == 200


def test_turnstile_middleware_blocks_protected_requests_without_session(monkeypatch):
    monkeypatch.setenv("TURNSTILE_ENABLED", "true")

    async def session_invalid(self, request):
        return False

    monkeypatch.setattr(TurnstileService, "is_session_valid", session_invalid)

    client = TestClient(_make_app())
    response = client.get("/api/v1/search")

    assert response.status_code == 403
    assert response.json()["error"] == "turnstile_required"
    assert response.headers["X-Turnstile-Required"] == "true"


def test_turnstile_middleware_bypasses_localhost_when_local_turnstile_not_enabled(
    monkeypatch,
):
    monkeypatch.setenv("TURNSTILE_ENABLED", "true")
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("TURNSTILE_ENABLE_LOCAL", raising=False)
    monkeypatch.delenv("VITE_TURNSTILE_ENABLE_LOCAL", raising=False)

    async def session_invalid(self, request):
        raise AssertionError("Local dev requests should bypass Turnstile sessions")

    monkeypatch.setattr(TurnstileService, "is_session_valid", session_invalid)

    client = TestClient(_make_app(), base_url="http://localhost")
    response = client.get("/api/v1/search")

    assert response.status_code == 200


def test_turnstile_middleware_challenges_localhost_when_local_turnstile_enabled(
    monkeypatch,
):
    monkeypatch.setenv("TURNSTILE_ENABLED", "true")
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("TURNSTILE_ENABLE_LOCAL", "true")

    async def session_invalid(self, request):
        return False

    monkeypatch.setattr(TurnstileService, "is_session_valid", session_invalid)

    client = TestClient(_make_app(), base_url="http://localhost")
    response = client.get("/api/v1/search")

    assert response.status_code == 403
    assert response.json()["error"] == "turnstile_required"


def test_turnstile_middleware_allows_verified_session(monkeypatch):
    monkeypatch.setenv("TURNSTILE_ENABLED", "true")

    async def session_valid(self, request):
        return True

    monkeypatch.setattr(TurnstileService, "is_session_valid", session_valid)

    client = TestClient(_make_app())
    response = client.get("/api/v1/search")

    assert response.status_code == 200


def test_turnstile_middleware_bypasses_api_key_requests(monkeypatch):
    monkeypatch.setenv("TURNSTILE_ENABLED", "true")

    async def session_invalid(self, request):
        raise AssertionError("API-key requests should bypass Turnstile session lookup")

    monkeypatch.setattr(TurnstileService, "is_session_valid", session_invalid)

    client = TestClient(_make_app())
    response = client.get("/api/v1/search", headers={"X-API-Key": "test-key"})

    assert response.status_code == 200


def test_turnstile_middleware_challenges_frontend_bff_even_with_api_key(monkeypatch):
    monkeypatch.setenv("TURNSTILE_ENABLED", "true")

    async def session_invalid(self, request):
        return False

    monkeypatch.setattr(TurnstileService, "is_session_valid", session_invalid)

    client = TestClient(_make_app())
    response = client.get(
        "/api/v1/search",
        headers={
            "X-API-Key": "frontend-key",
            "X-BTAA-Turnstile-Gate": "frontend-search",
        },
    )

    assert response.status_code == 403


def test_turnstile_middleware_ignores_unprotected_paths(monkeypatch):
    monkeypatch.setenv("TURNSTILE_ENABLED", "true")

    async def session_invalid(self, request):
        raise AssertionError("Unprotected paths should not check Turnstile sessions")

    monkeypatch.setattr(TurnstileService, "is_session_valid", session_invalid)

    client = TestClient(_make_app())
    response = client.get("/api/v1/resources/example")

    assert response.status_code == 200
