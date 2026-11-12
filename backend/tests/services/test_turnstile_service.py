import uuid
from urllib.parse import parse_qs

import httpx
import pytest
from fastapi import Request

from app.services.turnstile_service import TurnstileService


@pytest.fixture
def verification(monkeypatch):
    monkeypatch.setenv("TURNSTILE_ENABLED", "true")
    monkeypatch.setenv("TURNSTILE_SECRET_KEY", "dummy-secret")
    monkeypatch.setenv("TURNSTILE_EXPECTED_ACTION", "geoportal_gate")
    monkeypatch.setenv("TURNSTILE_ALLOWED_HOSTNAMES", "example.com")
    monkeypatch.delenv("TURNSTILE_SITEVERIFY_URL", raising=False)
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/",
            "headers": [],
            "client": ("192.0.2.1", 1234),
        }
    )
    return TurnstileService(), request


def install_transport(monkeypatch, handler):
    original = httpx.AsyncClient
    monkeypatch.setattr(
        "app.services.turnstile_service.httpx.AsyncClient",
        lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs),
    )

    async def no_sleep(_seconds):
        pass

    monkeypatch.setattr("app.services.turnstile_service.asyncio.sleep", no_sleep)


SUCCESS = {"success": True, "action": "geoportal_gate", "hostname": "example.com"}


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["timeout", "http-503", "internal-error"])
async def test_retries_transient_failures_with_same_uuid_and_token(
    monkeypatch, verification, failure
):
    calls = []

    def handler(request):
        calls.append(parse_qs(request.content.decode()))
        if len(calls) == 1:
            if failure == "timeout":
                raise httpx.ReadTimeout("simulated", request=request)
            if failure == "http-503":
                return httpx.Response(503)
            return httpx.Response(200, json={"success": False, "error-codes": ["internal-error"]})
        return httpx.Response(200, json=SUCCESS)

    install_transport(monkeypatch, handler)
    service, request = verification
    result = await service.verify_token("single-use-token", request)
    assert result.success
    assert len(calls) == 2
    assert calls[0] == calls[1]
    assert uuid.UUID(calls[0]["idempotency_key"][0]).version == 4
    assert calls[0]["response"] == ["single-use-token"]
    assert calls[0]["remoteip"] == ["192.0.2.1"]


@pytest.mark.asyncio
async def test_stops_after_three_transport_attempts(monkeypatch, verification):
    calls = []

    def handler(request):
        calls.append(request)
        raise httpx.ConnectError("simulated", request=request)

    install_transport(monkeypatch, handler)
    service, request = verification
    result = await service.verify_token("token", request)
    assert len(calls) == 3
    assert result.status_code == 503
    assert result.error_codes == ["siteverify-unavailable"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload", [[], None, {"success": "true"}, {"success": True, "error-codes": "bad"}]
)
async def test_malformed_response_fails_closed(monkeypatch, verification, payload):
    install_transport(monkeypatch, lambda request: httpx.Response(200, json=payload))
    service, request = verification
    result = await service.verify_token("token", request)
    assert not result.success
    assert result.status_code == 503


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload,code",
    [
        ({"success": False, "error-codes": ["timeout-or-duplicate"]}, "timeout-or-duplicate"),
        ({**SUCCESS, "action": "wrong"}, "invalid-action"),
        ({**SUCCESS, "hostname": "other.example"}, "invalid-hostname"),
    ],
)
async def test_does_not_retry_rejected_tokens_or_accept_mismatched_context(
    monkeypatch, verification, payload, code
):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json=payload)

    install_transport(monkeypatch, handler)
    service, request = verification
    result = await service.verify_token("token", request)
    assert len(calls) == 1
    assert not result.success
    assert result.error_codes == [code]


@pytest.mark.asyncio
async def test_oversized_token_is_not_sent_to_cloudflare(monkeypatch, verification):
    def unexpected(request):
        raise AssertionError("Oversized token must be rejected locally")

    install_transport(monkeypatch, unexpected)
    service, request = verification
    result = await service.verify_token("x" * 2049, request)
    assert result.status_code == 400
    assert not result.success
