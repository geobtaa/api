import pytest
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

    @app.post("/api/v1/search")
    async def post_search():
        return {"ok": True}

    @app.get("/api/v1/search/facets/{facet_name}")
    async def search_facet(facet_name: str):
        return {"ok": True, "facet": facet_name}

    @app.get("/api/v1/suggest")
    async def suggest():
        return {"ok": True}

    @app.get("/api/v1/map/h3")
    async def map_h3():
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


@pytest.mark.parametrize(
    ("method", "path", "headers", "params", "json"),
    [
        ("GET", "/api/v1/search", {}, None, None),
        ("GET", "/api/v1/search", {"Origin": "https://gin.btaa.org"}, None, None),
        (
            "GET",
            "/api/v1/search",
            {"User-Agent": "Mozilla/5.0 Safari/605.1.15"},
            None,
            None,
        ),
        (
            "GET",
            "/api/v1/search",
            {"Referer": "https://gin.btaa.org/api/specification/endpoints/"},
            None,
            None,
        ),
        (
            "GET",
            "/api/v1/search",
            {"Accept": "text/html,application/xhtml+xml"},
            None,
            None,
        ),
        (
            "GET",
            "/api/v1/search",
            {"X-BTAA-Client-Channel": "documentation"},
            None,
            None,
        ),
        ("GET", "/api/v1/search", {"X-Requested-With": "XMLHttpRequest"}, None, None),
        ("GET", "/api/v1/search", {"Authorization": "Bearer test-key"}, None, None),
        ("GET", "/api/v1/search", {}, {"api_key": "test-key"}, None),
        ("POST", "/api/v1/search", {}, None, {"q": "water"}),
        ("GET", "/api/v1/search/facets/schema_provider_s", {}, None, None),
        ("GET", "/api/v1/suggest", {}, {"q": "wat"}, None),
        ("GET", "/api/v1/map/h3", {}, None, None),
    ],
)
def test_turnstile_middleware_never_blocks_direct_public_api_requests(
    monkeypatch,
    method,
    path,
    headers,
    params,
    json,
):
    monkeypatch.setenv("TURNSTILE_ENABLED", "true")

    async def session_invalid(self, request):
        raise AssertionError("Direct public API requests must not check Turnstile sessions")

    monkeypatch.setattr(TurnstileService, "is_session_valid", session_invalid)

    client = TestClient(_make_app())
    response = client.request(method, path, headers=headers, params=params, json=json)

    assert response.status_code == 200


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
    response = client.get("/api/v1/search", headers={"X-BTAA-Client-Channel": "browser"})

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
    response = client.get("/api/v1/search", headers={"X-BTAA-Client-Channel": "browser"})

    assert response.status_code == 403
    assert response.json()["error"] == "turnstile_required"


def test_turnstile_middleware_allows_verified_session(monkeypatch):
    monkeypatch.setenv("TURNSTILE_ENABLED", "true")

    async def session_valid(self, request):
        return True

    monkeypatch.setattr(TurnstileService, "is_session_valid", session_valid)

    client = TestClient(_make_app())
    response = client.get("/api/v1/search", headers={"X-BTAA-Client-Channel": "browser"})

    assert response.status_code == 200


def test_turnstile_middleware_bypasses_api_key_requests(monkeypatch):
    monkeypatch.setenv("TURNSTILE_ENABLED", "true")

    async def session_invalid(self, request):
        raise AssertionError("API-key requests should bypass Turnstile session lookup")

    monkeypatch.setattr(TurnstileService, "is_session_valid", session_invalid)

    client = TestClient(_make_app())
    response = client.get("/api/v1/search", headers={"X-API-Key": "test-key"})

    assert response.status_code == 200


def test_turnstile_middleware_bypasses_cli_requests_without_api_key(monkeypatch):
    monkeypatch.setenv("TURNSTILE_ENABLED", "true")

    async def session_invalid(self, request):
        raise AssertionError("CLI requests should fall through to API rate limiting")

    monkeypatch.setattr(TurnstileService, "is_session_valid", session_invalid)

    client = TestClient(_make_app())
    response = client.get(
        "/api/v1/search",
        headers={
            "X-BTAA-Client-Name": "btaa-geo-api-cli",
            "X-BTAA-Client-Channel": "cli",
        },
    )

    assert response.status_code == 200


def test_turnstile_middleware_bypasses_cli_user_agent_without_api_key(monkeypatch):
    monkeypatch.setenv("TURNSTILE_ENABLED", "true")

    async def session_invalid(self, request):
        raise AssertionError("CLI user-agent requests should fall through to API rate limiting")

    monkeypatch.setattr(TurnstileService, "is_session_valid", session_invalid)

    client = TestClient(_make_app())
    response = client.get(
        "/api/v1/search",
        headers={"User-Agent": "BTAA-Geo-API-CLI/0.1.0"},
    )

    assert response.status_code == 200


def test_turnstile_middleware_bypasses_qgis_user_agent_without_api_key(monkeypatch):
    monkeypatch.setenv("TURNSTILE_ENABLED", "true")

    async def session_invalid(self, request):
        raise AssertionError("Desktop user-agent requests should fall through to API rate limiting")

    monkeypatch.setattr(TurnstileService, "is_session_valid", session_invalid)

    client = TestClient(_make_app())
    response = client.get(
        "/api/v1/search",
        headers={"User-Agent": "BTAA-QGIS-Plugin/0.1.0"},
    )

    assert response.status_code == 200


@pytest.mark.parametrize(
    "user_agent",
    [
        "Mozilla/5.0 AppleWebKit/537.36 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
        "Googlebot-Image/1.0",
        "Mozilla/5.0 AppleWebKit/537.36 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)",
        "DuckDuckBot/1.1; (+http://duckduckgo.com/duckduckbot.html)",
        "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)",
        "Twitterbot/1.0",
        "LinkedInBot/1.0",
        "Applebot/0.1",
    ],
)
def test_turnstile_middleware_bypasses_friendly_crawlers_for_frontend_gate_requests(
    monkeypatch,
    user_agent,
):
    monkeypatch.setenv("TURNSTILE_ENABLED", "true")

    async def session_invalid(self, request):
        raise AssertionError("Friendly crawlers should bypass Turnstile session lookup")

    monkeypatch.setattr(TurnstileService, "is_session_valid", session_invalid)

    client = TestClient(_make_app())
    response = client.get(
        "/api/v1/search",
        headers={
            "User-Agent": user_agent,
            "X-BTAA-Turnstile-Gate": "frontend-search",
            "X-BTAA-Client-Channel": "browser",
        },
    )

    assert response.status_code == 200


@pytest.mark.parametrize("user_agent", ["WormlyBot/1.0", "AppSignalBot/1.0"])
def test_turnstile_middleware_bypasses_monitoring_bots_for_frontend_gate_requests(
    monkeypatch,
    user_agent,
):
    monkeypatch.setenv("TURNSTILE_ENABLED", "true")

    async def session_invalid(self, request):
        raise AssertionError("Monitoring bots should bypass Turnstile session lookup")

    monkeypatch.setattr(TurnstileService, "is_session_valid", session_invalid)

    client = TestClient(_make_app())
    response = client.get(
        "/api/v1/search",
        headers={
            "User-Agent": user_agent,
            "X-BTAA-Turnstile-Gate": "frontend-search",
        },
    )

    assert response.status_code == 200


@pytest.mark.parametrize(
    ("headers", "params"),
    [
        ({"X-BTAA-Client-Channel": "browser"}, None),
        ({"X-BTAA-Turnstile-Gate": "frontend-search"}, None),
        ({"X-Visit-Token": "visit-token"}, None),
        (
            {
                "Origin": "https://lib-geoportal-prd-web-01.oit.umn.edu",
                "X-BTAA-Client-Channel": "browser",
            },
            None,
        ),
        (
            {
                "X-API-Key": "frontend-key",
                "X-BTAA-Turnstile-Gate": "frontend-search",
            },
            None,
        ),
        (
            {
                "X-BTAA-Client-Channel": "script",
                "X-BTAA-Turnstile-Gate": "frontend-search",
            },
            None,
        ),
        ({"X-BTAA-Client-Channel": "browser"}, {"api_key": "frontend-key"}),
    ],
)
def test_turnstile_middleware_challenges_frontend_gate_requests_without_session(
    monkeypatch,
    headers,
    params,
):
    monkeypatch.setenv("TURNSTILE_ENABLED", "true")

    async def session_invalid(self, request):
        return False

    monkeypatch.setattr(TurnstileService, "is_session_valid", session_invalid)

    client = TestClient(_make_app())
    response = client.get("/api/v1/search", headers=headers, params=params)

    assert response.status_code == 403
    assert response.json()["error"] == "turnstile_required"
    assert response.headers["X-Turnstile-Required"] == "true"


def test_turnstile_middleware_ignores_unprotected_paths(monkeypatch):
    monkeypatch.setenv("TURNSTILE_ENABLED", "true")

    async def session_invalid(self, request):
        raise AssertionError("Unprotected paths should not check Turnstile sessions")

    monkeypatch.setattr(TurnstileService, "is_session_valid", session_invalid)

    client = TestClient(_make_app())
    response = client.get("/api/v1/resources/example")

    assert response.status_code == 200
