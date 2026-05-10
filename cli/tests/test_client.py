from __future__ import annotations

import httpx
import pytest

from btaa_geo_api_cli.client import BtaaApiClient, BtaaApiError
from btaa_geo_api_cli.config import CliConfig


def test_client_headers_include_cli_metadata_and_api_key():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(request.headers)
        return httpx.Response(200, json={"ok": True})

    client = BtaaApiClient(
        CliConfig(api_key="secret-key", client_instance="instance-1"),
        transport=httpx.MockTransport(handler),
    )

    client.get("/search")

    assert seen["x-api-key"] == "secret-key"
    assert seen["x-btaa-client-name"] == "btaa-geo-api-cli"
    assert seen["x-btaa-client-channel"] == "cli"
    assert seen["x-btaa-client-instance"] == "instance-1"
    assert seen["user-agent"].startswith("BTAA-Geo-API-CLI/")


def test_turnstile_error_exposes_error_code_and_message():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            json={
                "error": "turnstile_required",
                "message": "A verified browser session is required for this request.",
            },
        )

    client = BtaaApiClient(
        CliConfig(client_instance="instance-1"), transport=httpx.MockTransport(handler)
    )

    with pytest.raises(BtaaApiError) as exc_info:
        client.get("/search")

    assert exc_info.value.status_code == 403
    assert exc_info.value.error_code == "turnstile_required"
    assert "A verified browser session is required" in str(exc_info.value)
