from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.endpoint_modules.turnstile import router
from app.services.turnstile_service import TurnstileValidationResult


def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    return app


def test_turnstile_status_reports_disabled(monkeypatch):
    monkeypatch.setenv("TURNSTILE_ENABLED", "false")

    client = TestClient(_make_app())
    response = client.get("/api/v1/turnstile/status")

    assert response.status_code == 200
    attributes = response.json()["data"]["attributes"]
    assert attributes["enabled"] is False
    assert attributes["verified"] is True


def test_turnstile_verify_returns_session(monkeypatch):
    monkeypatch.setenv("TURNSTILE_ENABLED", "true")

    async def verify_token(self, token, request):
        return TurnstileValidationResult(
            success=True,
            payload={
                "success": True,
                "action": "geoportal_gate",
                "hostname": "testserver",
            },
        )

    async def create_session(self, request):
        return "session-token"

    monkeypatch.setattr(
        "app.services.turnstile_service.TurnstileService.verify_token",
        verify_token,
    )
    monkeypatch.setattr(
        "app.services.turnstile_service.TurnstileService.create_session",
        create_session,
    )

    client = TestClient(_make_app())
    response = client.post("/api/v1/turnstile/verify", json={"token": "cf-token"})

    assert response.status_code == 200
    attributes = response.json()["data"]["attributes"]
    assert attributes["verified"] is True
    assert attributes["session_token"] == "session-token"
    assert "btaa_turnstile_session=session-token" in response.headers["set-cookie"]


def test_turnstile_verify_rejects_failed_validation(monkeypatch):
    monkeypatch.setenv("TURNSTILE_ENABLED", "true")

    async def verify_token(self, token, request):
        return TurnstileValidationResult(
            success=False,
            error_codes=["invalid-input-response"],
            status_code=400,
        )

    monkeypatch.setattr(
        "app.services.turnstile_service.TurnstileService.verify_token",
        verify_token,
    )

    client = TestClient(_make_app())
    response = client.post("/api/v1/turnstile/verify", json={"token": "bad-token"})

    assert response.status_code == 400
    attributes = response.json()["data"]["attributes"]
    assert attributes["verified"] is False
    assert attributes["error_codes"] == ["invalid-input-response"]


def test_turnstile_verify_rejects_oversized_token(monkeypatch):
    async def unexpected(*args, **kwargs):
        raise AssertionError("Oversized tokens must not reach Siteverify")

    monkeypatch.setattr("app.services.turnstile_service.TurnstileService.verify_token", unexpected)
    response = TestClient(_make_app()).post("/api/v1/turnstile/verify", json={"token": "x" * 2049})
    assert response.status_code == 422


def test_turnstile_verify_does_not_issue_session_when_storage_fails(monkeypatch):
    monkeypatch.setenv("TURNSTILE_ENABLED", "true")

    async def verified(*args, **kwargs):
        return TurnstileValidationResult(success=True)

    async def unavailable(*args, **kwargs):
        raise ConnectionError("simulated storage failure")

    monkeypatch.setattr("app.services.turnstile_service.TurnstileService.verify_token", verified)
    monkeypatch.setattr(
        "app.services.turnstile_service.TurnstileService.create_session", unavailable
    )
    response = TestClient(_make_app()).post("/api/v1/turnstile/verify", json={"token": "cf-token"})
    assert response.status_code == 503
    assert response.json()["data"]["attributes"]["error_codes"] == ["session-store-unavailable"]
    assert "set-cookie" not in response.headers
