from __future__ import annotations

import pytest
import pytest_asyncio

from app.services.feedback_service import (
    FeedbackDeliveryUnavailable,
    FeedbackSubmission,
    send_feedback_email,
)


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_database():
    yield


@pytest_asyncio.fixture(scope="session", autouse=True)
async def db_connection():
    yield


@pytest_asyncio.fixture(autouse=True)
async def db_transaction():
    yield


def _submission(**overrides) -> FeedbackSubmission:
    values = {
        "name": "Ada Lovelace",
        "email_address": "ada@example.edu",
        "topic": "Question",
        "description": "Can this record link to a newer dataset?",
        "source_url": "https://geo.example.org/feedback",
        "user_agent": "pytest",
    }
    values.update(overrides)
    return FeedbackSubmission(**values)


def test_send_feedback_email_supports_sendmail(monkeypatch):
    calls = []

    def fake_run(cmd, *, input, check, timeout):
        calls.append(
            {
                "cmd": cmd,
                "input": input,
                "check": check,
                "timeout": timeout,
            }
        )

    monkeypatch.setenv("FEEDBACK_EMAIL_ENABLED", "true")
    monkeypatch.setenv("FEEDBACK_DELIVERY", "sendmail")
    monkeypatch.setenv("FEEDBACK_RECIPIENTS", "team-a@example.edu,team-b@example.edu")
    monkeypatch.setenv("SENDMAIL_PATH", "/usr/local/bin/sendmail")
    monkeypatch.setenv("SENDMAIL_ARGS", "-t -i")
    monkeypatch.setattr("app.services.feedback_service.subprocess.run", fake_run)

    result = send_feedback_email(_submission())

    assert result == {
        "sent": True,
        "delivery": "sendmail",
        "recipients": 2,
    }
    assert calls[0]["cmd"] == ["/usr/local/bin/sendmail", "-t", "-i"]
    assert calls[0]["check"] is True
    assert b"BTAA Geoportal Feedback: Question" in calls[0]["input"]
    assert b"Can this record link to a newer dataset?" in calls[0]["input"]


def test_send_feedback_email_ignores_honeypot(monkeypatch):
    calls = []

    monkeypatch.setenv("FEEDBACK_EMAIL_ENABLED", "true")
    monkeypatch.setenv("FEEDBACK_DELIVERY", "sendmail")
    monkeypatch.setattr(
        "app.services.feedback_service.subprocess.run",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    result = send_feedback_email(_submission(contact_info="please email me"))

    assert result == {"sent": False, "reason": "honeypot"}
    assert calls == []


def test_send_feedback_email_raises_without_smtp_host(monkeypatch):
    monkeypatch.setenv("FEEDBACK_EMAIL_ENABLED", "true")
    monkeypatch.setenv("FEEDBACK_DELIVERY", "smtp")
    monkeypatch.setenv("FEEDBACK_RECIPIENTS", "team@example.edu")
    monkeypatch.delenv("SMTP_HOST", raising=False)

    with pytest.raises(FeedbackDeliveryUnavailable):
        send_feedback_email(_submission())
