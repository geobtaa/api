from unittest.mock import Mock

import pytest
import redis
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.endpoint_modules.analytics_auth import router
from app.api.v1.endpoint_modules.analytics_reports import router as reports_router
from app.services import analytics_auth as auth


class MemoryStore:
    def __init__(self):
        self.values = {}
        self.ttls = {}

    def set(self, key, value, ex):
        self.values[key] = value
        self.ttls[key] = ex

    def get(self, key):
        return self.values.get(key)

    def getdel(self, key):
        return self.values.pop(key, None)

    def delete(self, key):
        self.values.pop(key, None)

    def eval(self, script, numkeys, key, ttl):
        self.values[key] = self.values.get(key, 0) + 1
        self.ttls[key] = ttl
        return self.values[key]


PASSWORD = "a-long-test-only-password-123"


@pytest.fixture
def setup(monkeypatch):
    store = MemoryStore()
    monkeypatch.setattr(auth, "store", lambda: store)
    monkeypatch.setenv("ANALYTICS_PASSWORD", PASSWORD)
    monkeypatch.setenv("ANALYTICS_BASE_URL", "https://testserver")
    app = FastAPI()
    app.include_router(router)
    app.include_router(reports_router)
    return TestClient(
        app, base_url="https://testserver", headers={"Origin": "https://testserver"}
    ), store


def login(client, password=PASSWORD):
    return client.post("/analytics/auth/password", json={"password": password})


def test_password_session_rotation_expiry_and_logout(setup):
    client, store = setup
    assert client.get("/analytics/auth/session").status_code == 401
    response = login(client)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, no-store"
    cookie = response.headers["set-cookie"]
    assert all(part in cookie for part in ["HttpOnly", "Secure", "SameSite=lax", "Max-Age=86400"])
    token = client.cookies.get(auth.COOKIE)
    key = "analytics:session:" + auth.digest(token)
    assert token not in store.values and PASSWORD not in str(store.values)
    assert store.ttls[key] == 86400
    assert client.get("/analytics/auth/session").json() == {"authenticated": True}
    assert login(client).status_code == 200
    assert key not in store.values
    assert client.cookies.get(auth.COOKIE) != token
    current = "analytics:session:" + auth.digest(client.cookies.get(auth.COOKIE))
    store.delete(current)
    assert client.get("/analytics/auth/session").status_code == 401
    login(client)
    response = client.post("/analytics/auth/logout")
    assert "Max-Age=0" in response.headers["set-cookie"]
    assert client.get("/analytics/auth/session").status_code == 401
    assert not any(key.startswith("analytics:session:") for key in store.values)


@pytest.mark.parametrize("password", ["wrong", PASSWORD.upper(), PASSWORD + " ", "🔒" * 20])
def test_wrong_password_denies_access(setup, password):
    client, store = setup
    response = login(client, password)
    assert response.status_code == 401
    assert "set-cookie" not in response.headers
    assert not any(key.startswith("analytics:session:") for key in store.values)


def test_unicode_password_matches_exactly(setup, monkeypatch):
    client, _ = setup
    secret = "library-review-password-🔒-é"
    monkeypatch.setenv("ANALYTICS_PASSWORD", secret)
    assert login(client, secret).status_code == 200
    assert login(client, secret + " ").status_code == 401
    assert login(client, secret.replace("é", "e")).status_code == 401


def test_password_rotation_revokes_existing_sessions(setup, monkeypatch):
    client, _ = setup
    login(client)
    monkeypatch.setenv("ANALYTICS_PASSWORD", "another-long-test-password-456")
    assert client.get("/analytics/auth/session").status_code == 401
    assert login(client).status_code == 401
    assert login(client, "another-long-test-password-456").status_code == 200


@pytest.mark.parametrize("secret", ["", "short"])
def test_unconfigured_password_fails_closed(setup, monkeypatch, secret):
    client, _ = setup
    login(client)
    monkeypatch.setenv("ANALYTICS_PASSWORD", secret)
    assert login(client).status_code == 503
    assert client.get("/analytics/auth/session").status_code == 503


def test_rate_limit_cannot_be_bypassed_using_forwarded_headers(setup):
    client, _ = setup
    for i in range(30):
        response = client.post(
            "/analytics/auth/password",
            json={"password": "wrong"},
            headers={"X-Forwarded-For": f"192.0.2.{i}"},
        )
        assert response.status_code == 401
    response = login(client)
    assert response.status_code == 429
    assert response.headers["retry-after"] == "900"


def test_redis_failure_denies_access(setup, monkeypatch):
    client, store = setup
    login(client)
    monkeypatch.setattr(auth, "store", Mock(side_effect=redis.RedisError))
    assert login(client).status_code == 503
    assert client.get("/analytics/auth/session").status_code == 503
    assert client.post("/analytics/auth/logout").status_code == 503


@pytest.mark.parametrize("path", ["password", "logout"])
def test_cross_origin_posts_are_rejected(setup, path):
    client, _ = setup
    assert (
        client.post(
            "/analytics/auth/" + path,
            json={"password": PASSWORD},
            headers={"Origin": "https://evil.example"},
        ).status_code
        == 403
    )


@pytest.mark.parametrize("payload", [{}, {"password": ""}, {"password": "x" * 1025}])
def test_invalid_password_input(setup, payload):
    client, _ = setup
    assert client.post("/analytics/auth/password", json=payload).status_code == 422


def test_legacy_auth_routes_and_sessions_are_disabled(setup):
    client, store = setup
    for route in ["request", "verify", "google/start", "google/callback"]:
        assert client.post("/analytics/auth/" + route, json={}).status_code == 404
    token = "a" * 43
    store.set("analytics:session:" + auth.digest(token), "reader@example.org", ex=86400)
    client.cookies.set(auth.COOKIE, token)
    assert client.get("/analytics/auth/session").status_code == 401


def test_downloads_require_authentication(setup):
    client, _ = setup
    assert client.get("/analytics/reports/manifest").status_code == 401
