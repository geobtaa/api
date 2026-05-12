from __future__ import annotations

import hashlib
import hmac
import time
from urllib.parse import urlencode

from app.services.slackbot_service import SIGNATURE_VERSION


def _signature(secret: str, body: bytes, timestamp: str) -> str:
    base_string = b":".join([SIGNATURE_VERSION.encode(), timestamp.encode(), body])
    digest = hmac.new(secret.encode(), base_string, hashlib.sha256).hexdigest()
    return f"{SIGNATURE_VERSION}={digest}"


def test_slack_info_endpoint_reports_configuration(client, monkeypatch):
    monkeypatch.setenv("SLACK_SIGNING_SECRET", "test-secret")

    response = client.get("/api/v1/slack")

    assert response.status_code == 200
    assert response.json()["command_endpoint"] == "/api/v1/slack/commands"
    assert response.json()["configured"] is True


def test_slack_command_rejects_bad_signature(client, monkeypatch):
    monkeypatch.setenv("SLACK_SIGNING_SECRET", "test-secret")

    response = client.post(
        "/api/v1/slack/commands",
        content=urlencode({"text": "help"}),
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "X-Slack-Request-Timestamp": "1000",
            "X-Slack-Signature": "v0=bad",
        },
    )

    assert response.status_code == 401


def test_slack_command_dispatches_valid_signed_payload(client, monkeypatch):
    secret = "test-secret"
    body = urlencode({"text": "help"}).encode()
    timestamp = str(int(time.time()))
    monkeypatch.setenv("SLACK_SIGNING_SECRET", secret)

    response = client.post(
        "/api/v1/slack/commands",
        content=body,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "X-Slack-Request-Timestamp": timestamp,
            "X-Slack-Signature": _signature(secret, body, timestamp),
        },
    )

    assert response.status_code == 200
    assert response.json()["response_type"] == "ephemeral"
    assert "BTAA Geoportal" in response.json()["blocks"][0]["text"]["text"]
