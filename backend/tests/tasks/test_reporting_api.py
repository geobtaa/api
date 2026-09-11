from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.endpoint_modules import analytics, analytics_reports


def test_shadow_mode_is_closed(monkeypatch):
    monkeypatch.delenv("ANALYTICS_REPORTS_PUBLIC", raising=False)
    app = FastAPI()
    app.include_router(analytics_reports.router)
    assert TestClient(app).get("/analytics/reports/manifest").status_code == 503


def test_downloads_only_publish_approved_tables_and_escape_formulas(monkeypatch):
    monkeypatch.setattr(
        analytics_reports,
        "read_document",
        lambda *args: {"queries": [{"query": "=1+1", "count": 3, "context": {"page": ["1"]}}]},
    )
    app = FastAPI()
    app.include_router(analytics_reports.router)
    client = TestClient(app)
    base = "/analytics/reports/2026-07/" + "a" * 64 + "/download/"
    response = client.get(base + "queries")
    assert response.status_code == 200
    assert "'=1+1" in response.text
    assert "attachment" in response.headers["content-disposition"]
    assert client.get(base + "receipts").status_code == 404


def test_queue_failure_is_not_reported_as_accepted(monkeypatch):
    class FailedQueue:
        def delay(self, payload):
            raise RuntimeError("queue down")

    monkeypatch.setattr(analytics, "write_analytics_batch", FailedQueue())
    monkeypatch.delenv("DISABLE_ANALYTICS_EVENTS", raising=False)
    app = FastAPI()
    app.include_router(analytics.router)
    response = TestClient(app).post("/analytics/events", json={"searches": [{"search_id": "a"}]})
    assert response.status_code == 503
    assert response.headers["retry-after"] == "5"
