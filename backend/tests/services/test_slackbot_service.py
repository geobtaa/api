from __future__ import annotations

import hashlib
import hmac

import pytest

from app.services.slackbot_service import (
    SIGNATURE_VERSION,
    handle_slack_command,
    parse_slack_command,
    verify_slack_signature,
)


def _signature(secret: str, body: bytes, timestamp: str) -> str:
    base_string = b":".join([SIGNATURE_VERSION.encode(), timestamp.encode(), body])
    digest = hmac.new(secret.encode(), base_string, hashlib.sha256).hexdigest()
    return f"{SIGNATURE_VERSION}={digest}"


def test_verify_slack_signature_accepts_valid_signature():
    secret = "test-secret"
    body = b"text=search+minnesota"
    timestamp = "1000"

    assert verify_slack_signature(
        signing_secret=secret,
        body=body,
        timestamp=timestamp,
        signature=_signature(secret, body, timestamp),
        now=1000,
    )


def test_verify_slack_signature_rejects_stale_request():
    secret = "test-secret"
    body = b"text=search+minnesota"
    timestamp = "1000"

    assert not verify_slack_signature(
        signing_secret=secret,
        body=body,
        timestamp=timestamp,
        signature=_signature(secret, body, timestamp),
        now=2000,
    )


def test_parse_slack_command_defaults_to_help():
    command = parse_slack_command("")

    assert command.action == "help"
    assert command.query is None


def test_parse_slack_command_treats_bare_text_as_search():
    command = parse_slack_command("sanborn maps")

    assert command.action == "search"
    assert command.query == "sanborn maps"


@pytest.mark.asyncio
async def test_handle_slack_command_returns_search_blocks(monkeypatch):
    class FakeSearchService:
        async def search(self, **_kwargs):
            return {
                "meta": {"totalCount": 12},
                "data": [
                    {
                        "id": "abc123",
                        "attributes": {
                            "title": "Historic Lake Map",
                            "provider": "University of Minnesota",
                            "year": 1912,
                        },
                    }
                ],
            }

    monkeypatch.setattr("app.services.slackbot_service.SearchService", FakeSearchService)
    monkeypatch.setenv("GEOPORTAL_BASE_URL", "https://geoportal.example.edu")

    response = await handle_slack_command({"text": ["search lakes"]})

    assert response["response_type"] == "ephemeral"
    assert "lakes" in response["text"]
    block_text = "\n".join(
        block["text"]["text"] for block in response["blocks"] if block["type"] == "section"
    )
    assert "Historic Lake Map" in block_text
    assert "https://geoportal.example.edu/resources/abc123" in block_text
