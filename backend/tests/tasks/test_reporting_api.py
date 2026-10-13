from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.endpoint_modules import analytics, analytics_reports


def test_shadow_mode_is_closed(monkeypatch):
    monkeypatch.delenv("ANALYTICS_REPORTS_PUBLIC", raising=False)
    app = FastAPI()
    app.dependency_overrides[analytics_reports.require_analytics_session] = (
        lambda: "reader@example.org"
    )
    app.include_router(analytics_reports.router)
    assert TestClient(app).get("/analytics/reports/manifest").status_code == 503


def test_downloads_only_publish_approved_tables_and_escape_formulas(monkeypatch):
    document = {
        "period": "2026-07",
        "calculationVersion": "1",
        "start": "2026-07-01",
        "endExclusive": "2026-08-01",
        "daily": [{"date": "2026-07-01", "requests": 3}],
    }
    monkeypatch.setattr(analytics_reports, "read_document", lambda *args: document)
    app = FastAPI()
    app.dependency_overrides[analytics_reports.require_analytics_session] = (
        lambda: "reader@example.org"
    )
    app.include_router(analytics_reports.router)
    client = TestClient(app)
    revision = analytics_reports.public_report(document)["revision"]
    base = "/analytics/reports/2026-07/" + revision + "/download/"
    response = client.get(base + "daily")
    assert response.status_code == 200
    assert "2026-07-01,3" in response.text
    assert "attachment" in response.headers["content-disposition"]
    assert client.get(base + "daily?format=json").json() == document["daily"]
    assert client.get(base + "receipts").status_code == 404
    assert client.get(base + "queries").status_code == 404
    assert analytics_reports.csv_cell("=1+1") == "'=1+1"


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


def test_reporting_openapi_uses_standard_errors_and_typed_success():
    from app.api.errors import COMMON_ERROR_RESPONSES

    app = FastAPI()
    app.dependency_overrides[analytics_reports.require_analytics_session] = (
        lambda: "reader@example.org"
    )
    app.include_router(analytics_reports.router)
    schema = app.openapi()
    for path in schema["paths"].values():
        response = path["get"]["responses"]
        for status in COMMON_ERROR_RESPONSES:
            assert str(status) in response
        assert response["200"]["content"]["application/json"]["schema"]


def test_evidence_download_is_screened_and_does_not_claim_source_replay(monkeypatch):
    document = analytics_reports.public_report(
        {
            "period": "2026-09",
            "calculationVersion": "3",
            "start": "2026-09-01",
            "endExclusive": "2026-10-01",
            "totals": {"requests": 3},
            "daily": [{"date": "2026-09-01", "requests": 3}],
            "receipts": [{"source_id": "private"}],
        }
    )
    monkeypatch.setattr(analytics_reports, "read_document", lambda *args: document)
    app = FastAPI()
    app.dependency_overrides[analytics_reports.require_analytics_session] = (
        lambda: "reader@example.org"
    )
    app.include_router(analytics_reports.router)
    client = TestClient(app)
    path = f"/analytics/reports/2026-09/{document['revision']}/evidence"
    response = client.get(path)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, no-store"
    assert response.json()["report"] == document
    assert response.json()["evidence"]["verification"]["preservedInputReplay"] == "not-verified"
    assert "source_id" not in response.text
    assert client.get(path.replace(document["revision"], "a" * 64)).status_code == 404
