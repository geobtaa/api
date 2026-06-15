import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.endpoint_modules.feedback import router
from app.services.feedback_service import FeedbackDeliveryUnavailable


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_database():
    yield


@pytest_asyncio.fixture(scope="session", autouse=True)
async def db_connection():
    yield


@pytest_asyncio.fixture(autouse=True)
async def db_transaction():
    yield


def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    return app


def test_submit_feedback_sends_email(monkeypatch):
    submissions = []

    def fake_send_feedback_email(submission):
        submissions.append(submission)
        return {"sent": True, "delivery": "sendmail", "recipients": 1}

    monkeypatch.setattr(
        "app.api.v1.endpoint_modules.feedback.send_feedback_email",
        fake_send_feedback_email,
    )

    client = TestClient(_make_app())
    response = client.post(
        "/api/v1/feedback",
        json={
            "name": "Ada Lovelace",
            "email_address": "ada@example.edu",
            "topic": "Comments or Suggestions",
            "description": "The new search page is helpful.",
            "source_url": "https://geo.example.org/feedback",
            "user_agent": "pytest",
        },
    )

    assert response.status_code == 202
    attributes = response.json()["data"]["attributes"]
    assert attributes == {"accepted": True, "sent": True}
    assert submissions[0].topic == "Comments or Suggestions"
    assert submissions[0].description == "The new search page is helpful."


def test_submit_feedback_rejects_unknown_topic():
    client = TestClient(_make_app())
    response = client.post(
        "/api/v1/feedback",
        json={
            "topic": "Nope",
            "description": "Feedback body",
        },
    )

    assert response.status_code == 422


def test_submit_feedback_reports_delivery_unavailable(monkeypatch):
    def fake_send_feedback_email(submission):
        raise FeedbackDeliveryUnavailable("no_smtp_host")

    monkeypatch.setattr(
        "app.api.v1.endpoint_modules.feedback.send_feedback_email",
        fake_send_feedback_email,
    )

    client = TestClient(_make_app())
    response = client.post(
        "/api/v1/feedback",
        json={
            "topic": "Question",
            "description": "Can someone follow up?",
        },
    )

    assert response.status_code == 503
    assert response.json()["message"] == "Feedback delivery is temporarily unavailable."
