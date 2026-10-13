import json
import re
from email.utils import parsedate_to_datetime
from unittest.mock import Mock

import pytest
import pytest_asyncio
import redis
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.endpoint_modules.analytics_auth import router
from app.api.v1.endpoint_modules.analytics_reports import router as reports_router
from app.services import analytics_auth as auth


@pytest_asyncio.fixture(scope="session", autouse=True)
async def db_connection():
    yield


@pytest_asyncio.fixture(autouse=True)
async def db_transaction():
    yield


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


@pytest.fixture
def setup(monkeypatch):
    store = MemoryStore()
    sent = []
    monkeypatch.setattr(auth, "store", lambda: store)
    monkeypatch.setattr(auth, "deliver_email", sent.append)
    monkeypatch.setenv("ANALYTICS_APPROVED_EMAILS", "reader@example.org,person@uwmadison.edu")
    monkeypatch.delenv("ANALYTICS_APPROVED_EMAILS_FILE", raising=False)
    monkeypatch.setenv("ANALYTICS_BASE_URL", "https://testserver")
    app = FastAPI()
    app.include_router(router)
    app.include_router(reports_router)
    client = TestClient(
        app, base_url="https://testserver", headers={"Origin": "https://testserver"}
    )
    return client, store, sent


def request_token(client, sent, email="reader@example.org"):
    assert client.post("/analytics/auth/request", json={"email": email}).status_code == 202
    return re.search(r"#token=([\w-]+)", sent[-1].get_content()).group(1)


def test_external_email_single_use_session_and_logout(setup):
    client, store, sent = setup
    token = request_token(client, sent, " Person@UWMADISON.edu ")
    assert str(sent[0]["From"]) == "BTAA Geoportal <no-reply@geo.btaa.org>"
    assert sent[0]["To"] == "person@uwmadison.edu"
    assert parsedate_to_datetime(sent[0]["Date"]).tzinfo is not None
    assert re.fullmatch(r"<[^<>\s]+@geo\.btaa\.org>", sent[0]["Message-ID"])
    assert token not in str(store.values)
    assert store.ttls["analytics:link:" + auth.digest(token)] == 86400
    response = client.post("/analytics/auth/verify", json={"token": token})
    assert response.status_code == 200
    cookie = response.headers["set-cookie"]
    assert all(value in cookie for value in ("HttpOnly", "Secure", "SameSite=lax", "Max-Age=86400"))
    assert client.post("/analytics/auth/verify", json={"token": token}).status_code == 400
    assert client.get("/analytics/auth/session").json() == {"email": "person@uwmadison.edu"}
    old_cookie = client.cookies.get(auth.COOKIE)
    assert client.post("/analytics/auth/logout").status_code == 200
    client.cookies.set(auth.COOKIE, old_cookie)
    assert client.get("/analytics/auth/session").status_code == 401


def test_unknown_address_same_response_and_rate_limit(setup):
    client, store, sent = setup
    unknown = client.post("/analytics/auth/request", json={"email": "unknown@example.org"})
    known = client.post("/analytics/auth/request", json={"email": "reader@example.org"})
    assert unknown.status_code == known.status_code == 202
    assert unknown.json() == known.json()
    for _ in range(5):
        client.post("/analytics/auth/request", json={"email": "reader@example.org"})
    assert len(sent) == 3
    store.values["analytics:rate:ip:" + auth.digest("testclient")] = 100
    assert (
        client.post("/analytics/auth/request", json={"email": "other@example.org"}).status_code
        == 429
    )


def test_revocation_expiry_and_unavailable_store(setup, monkeypatch, tmp_path):
    client, store, sent = setup
    token = request_token(client, sent)
    store.delete("analytics:link:" + auth.digest(token))
    assert client.post("/analytics/auth/verify", json={"token": token}).status_code == 400
    token = request_token(client, sent)
    client.post("/analytics/auth/verify", json={"token": token})
    filename = tmp_path / "approved.json"
    filename.write_text(json.dumps(["reader@example.org"]))
    monkeypatch.setenv("ANALYTICS_APPROVED_EMAILS_FILE", str(filename))
    assert client.get("/analytics/auth/session").status_code == 200
    filename.write_text("[]")
    assert client.get("/analytics/auth/session").status_code == 401
    filename.write_text("broken")
    assert client.get("/analytics/auth/session").status_code == 401
    monkeypatch.setattr(auth, "store", Mock(side_effect=redis.ConnectionError))
    assert client.get("/analytics/auth/session").status_code == 503


def test_protects_every_report_endpoint_before_reading_data(setup, monkeypatch):
    from app.api.v1.endpoint_modules import analytics_reports

    client, _, _ = setup
    read = Mock(side_effect=AssertionError("Must not read private data"))
    monkeypatch.setattr(analytics_reports, "read_document", read)
    revision = "a" * 64
    for path in (
        "manifest",
        f"all/{revision}",
        f"all/{revision}/download/queries?format=json",
        f"all/{revision}/download/queries",
    ):
        assert client.get("/analytics/reports/" + path).status_code == 401
    read.assert_not_called()


def test_cross_origin_requests_rejected_and_scanners_cannot_consume_links(setup):
    client, store, sent = setup
    token = request_token(client, sent)
    for endpoint, body in (
        ("request", {"email": "reader@example.org"}),
        ("verify", {"token": token}),
        ("logout", {}),
    ):
        assert (
            client.post(
                "/analytics/auth/" + endpoint, json=body, headers={"Origin": "https://evil.example"}
            ).status_code
            == 403
        )
    assert client.get("/analytics/auth/verify?token=" + token).status_code == 405
    assert store.get("analytics:link:" + auth.digest(token))


def test_delivery_failure_invalidates_link_without_exposing_details(setup, monkeypatch, caplog):
    client, store, sent = setup
    monkeypatch.setattr(auth, "deliver_email", Mock(side_effect=OSError("private-recipient")))
    response = client.post("/analytics/auth/request", json={"email": "reader@example.org"})
    assert response.status_code == 202
    assert not any(key.startswith("analytics:link:") for key in store.values)
    assert "private-recipient" not in caplog.text


def test_local_preview_captures_email_without_smtp(setup, monkeypatch):
    from app.services.feedback_service import deliver_email

    client, store, sent = setup
    monkeypatch.setattr(auth, "deliver_email", deliver_email)
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("FEEDBACK_DELIVERY", "preview")
    monkeypatch.setenv("ANALYTICS_BASE_URL", "http://localhost:3000")
    response = client.post(
        "/analytics/auth/request",
        json={"email": "reader@example.org"},
        headers={"Origin": "http://localhost:3000"},
    )
    mail = response.json()["preview"]
    assert mail["to"] == "reader@example.org"
    assert "http://localhost:3000/analytics/login#token=" in mail["body"]
    assert response.headers["cache-control"] == "private, no-store"


@pytest.mark.parametrize(
    "environment,url",
    [("production", "http://localhost:3000"), ("development", "https://example.org")],
)
def test_preview_never_exposes_tokens_outside_local_development(
    setup, monkeypatch, environment, url
):
    from app.services.feedback_service import deliver_email

    client, store, sent = setup
    monkeypatch.setattr(auth, "deliver_email", deliver_email)
    monkeypatch.setenv("APP_ENV", environment)
    monkeypatch.setenv("FEEDBACK_DELIVERY", "preview")
    monkeypatch.setenv("ANALYTICS_BASE_URL", url)
    response = client.post(
        "/analytics/auth/request", json={"email": "reader@example.org"}, headers={"Origin": url}
    )
    assert "preview" not in response.json()
    assert not any(key.startswith("analytics:link:") for key in store.values)


def test_local_preview_explains_unknown_address_and_request_limit(setup, monkeypatch):
    from app.services.feedback_service import deliver_email

    client, store, sent = setup
    monkeypatch.setattr(auth, "deliver_email", deliver_email)
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("FEEDBACK_DELIVERY", "preview")
    monkeypatch.setenv("ANALYTICS_BASE_URL", "http://localhost:3000")
    headers = {"Origin": "http://localhost:3000"}
    response = client.post(
        "/analytics/auth/request", json={"email": "unknown@example.org"}, headers=headers
    )
    assert "approved list" in response.json()["preview_error"]
    for _ in range(3):
        response = client.post(
            "/analytics/auth/request", json={"email": "reader@example.org"}, headers=headers
        )
        assert "preview" in response.json()
    response = client.post(
        "/analytics/auth/request", json={"email": "reader@example.org"}, headers=headers
    )
    assert response.status_code == 429


@pytest.mark.parametrize(
    "email",
    [
        "!" * 240,
        "a@" + "!" * 240,
        "a@@example.org",
        "a@.org",
        "a@example.",
        "a b@example.org",
        "a<@example.org",
    ],
)
def test_malformed_addresses_are_rejected_without_delivery(setup, email):
    client, store, sent = setup
    assert client.post("/analytics/auth/request", json={"email": email}).status_code == 422
    assert not sent
    assert not store.values


@pytest.fixture
def google_login(setup, monkeypatch):
    from app.services import analytics_google_auth as google

    client, store, sent = setup
    monkeypatch.setenv("ANALYTICS_GOOGLE_CLIENT_ID", "test-client")
    monkeypatch.setenv("ANALYTICS_GOOGLE_CLIENT_SECRET", "test-secret")
    monkeypatch.setenv("ANALYTICS_APPROVED_EMAILS", "reader@gmail.com,person@umn.edu")
    exchange = Mock(return_value=Mock(json=lambda: {"id_token": "signed-token"}))
    monkeypatch.setattr(google.httpx, "post", exchange)
    return client, store, google, exchange


def google_challenge(client, store):
    from urllib.parse import parse_qs, urlsplit

    response = client.post("/analytics/auth/google/start")
    assert response.status_code == 200
    query = {k: v[0] for k, v in parse_qs(urlsplit(response.json()["url"]).query).items()}
    record = json.loads(store.get("analytics:google:" + auth.digest(query["state"])))
    return query, record


def google_claims(query, **overrides):
    return dict(
        {
            "email": "reader@gmail.com",
            "email_verified": True,
            "sub": "google-user",
            "nonce": query["nonce"],
        },
        **overrides,
    )


def google_finish(client, query):
    return client.post(
        "/analytics/auth/google/callback", json={"code": "one-use-code", "state": query["state"]}
    )


def test_google_login_rotates_session_and_rejects_replay(google_login, monkeypatch):
    import base64
    import hashlib

    client, store, google, exchange = google_login
    assert client.get("/analytics/auth/options").json() == {"google": True}
    query, record = google_challenge(client, store)
    assert query["scope"] == "openid email"
    assert query["redirect_uri"] == "https://testserver/analytics/google/callback"
    assert query["code_challenge_method"] == "S256"
    assert query["code_challenge"] == base64.urlsafe_b64encode(
        hashlib.sha256(record["verifier"].encode()).digest()
    ).decode().rstrip("=")
    assert store.ttls["analytics:google:" + auth.digest(query["state"])] == 600
    verify = Mock(return_value=google_claims(query))
    monkeypatch.setattr(google.id_token, "verify_oauth2_token", verify)
    old = "z" * 43
    store.set("analytics:session:" + auth.digest(old), "reader@gmail.com", ex=86400)
    client.cookies.set(auth.COOKIE, old)
    response = google_finish(client, query)
    assert response.status_code == 200
    assert store.get("analytics:session:" + auth.digest(old)) is None
    cookies = response.headers.get_list("set-cookie")
    assert any("HttpOnly" in c and "Secure" in c and "Max-Age=86400" in c for c in cookies)
    assert any(google.COOKIE in c and "Max-Age=0" in c for c in cookies)
    assert verify.call_args.kwargs["audience"] == "test-client"
    assert exchange.call_args.kwargs["data"]["code_verifier"] == record["verifier"]
    assert google_finish(client, query).status_code == 400
    assert exchange.call_count == 1
    # Revoking approval also revokes an existing Google-authenticated session.
    client.cookies.clear()
    for cookie in response.cookies.jar:
        client.cookies.set(cookie.name, cookie.value)
    assert client.get("/analytics/auth/session").json() == {"email": "reader@gmail.com"}
    monkeypatch.setenv("ANALYTICS_APPROVED_EMAILS", "")
    assert client.get("/analytics/auth/session").status_code == 401


@pytest.mark.parametrize(
    "overrides",
    [
        {"email": "stranger@gmail.com"},
        {"email_verified": False},
        {"email_verified": "true"},
        {"nonce": "wrong"},
        {"sub": ""},
        {"email": None},
        {"email": "person@umn.edu"},  # Non-Gmail requires a managed Workspace identity.
    ],
)
def test_google_rejects_unapproved_or_unverified_identity(google_login, monkeypatch, overrides):
    client, store, google, _ = google_login
    query, _ = google_challenge(client, store)
    monkeypatch.setattr(
        google.id_token, "verify_oauth2_token", lambda *a, **k: google_claims(query, **overrides)
    )
    assert google_finish(client, query).status_code == 403
    assert not any(key.startswith("analytics:session:") for key in store.values)


def test_google_workspace_email_is_supported(google_login, monkeypatch):
    client, store, google, _ = google_login
    query, _ = google_challenge(client, store)
    monkeypatch.setattr(
        google.id_token,
        "verify_oauth2_token",
        lambda *a, **k: google_claims(query, email="Person@umn.edu", hd="umn.edu"),
    )
    assert google_finish(client, query).status_code == 200


@pytest.mark.parametrize("kind", ["missing_cookie", "wrong_cookie", "expired"])
def test_google_requires_same_browser_and_live_state(google_login, kind):
    client, store, google, exchange = google_login
    query, _ = google_challenge(client, store)
    if kind == "expired":
        store.delete("analytics:google:" + auth.digest(query["state"]))
    else:
        client.cookies.clear()
        if kind == "wrong_cookie":
            client.cookies.set(google.COOKIE, "other-browser")
    assert google_finish(client, query).status_code == 400
    exchange.assert_not_called()


def test_google_provider_failure_and_storage_failure_fail_closed(google_login, monkeypatch):
    client, store, google, exchange = google_login
    query, _ = google_challenge(client, store)
    exchange.side_effect = RuntimeError("provider secret response")
    response = google_finish(client, query)
    assert response.status_code == 400
    assert "secret" not in response.text
    monkeypatch.setattr(store, "getdel", Mock(side_effect=redis.RedisError))
    assert google_finish(client, query).status_code == 503


def test_google_configuration_and_origin_checks(setup, monkeypatch):
    client, _, _ = setup
    monkeypatch.delenv("ANALYTICS_GOOGLE_CLIENT_ID", raising=False)
    monkeypatch.delenv("ANALYTICS_GOOGLE_CLIENT_SECRET", raising=False)
    assert client.get("/analytics/auth/options").json() == {"google": False}
    assert client.post("/analytics/auth/google/start").status_code == 503
    for path in ["start", "callback"]:
        response = client.post(
            "/analytics/auth/google/" + path,
            headers={"Origin": "https://evil.example"},
            json={"code": "code", "state": "s" * 43},
        )
        assert response.status_code == 403


@pytest.mark.parametrize("invalid", [None, "audience", "issuer", "expired", "signature"])
def test_google_signed_tokens_are_validated(google_login, monkeypatch, invalid):
    """Exercise the real Google verifier with locally signed tokens, no network."""
    import time

    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from google.auth import crypt, jwt

    client, store, google, exchange = google_login
    query, _ = google_challenge(client, store)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )
    public = (
        key.public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )
    claims = google_claims(query)
    now = int(time.time())
    claims.update(
        aud="test-client", iss="https://accounts.google.com", iat=now - 60, exp=now + 3600
    )
    if invalid == "audience":
        claims["aud"] = "another-app"
    if invalid == "issuer":
        claims["iss"] = "https://evil.example"
    if invalid == "expired":
        claims.update(iat=now - 7200, exp=now - 3600)
    token = jwt.encode(crypt.RSASigner.from_string(private, key_id="test"), claims).decode()
    if invalid == "signature":
        head, body, signature = token.split(".")
        token = head + "." + body + "." + ("A" if signature[0] != "A" else "B") + signature[1:]
    exchange.return_value.json = lambda: {"id_token": token}
    monkeypatch.setattr(
        google,
        "BoundedGoogleRequest",
        lambda: Mock(return_value=Mock(status=200, data=json.dumps({"test": public}).encode())),
    )
    assert google_finish(client, query).status_code == (200 if invalid is None else 400)
