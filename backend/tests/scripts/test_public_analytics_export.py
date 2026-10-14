import copy

from app.services.analytics_reporting.public_export import public_report
from app.services.analytics_reporting.storage import checksum


def fixture():
    return {
        "period": "2026-09",
        "start": "2026-09-01",
        "endExclusive": "2026-10-01",
        "calculationVersion": "3",
        "complete": True,
        "totals": {"requests": 10},
        "daily": [{"date": "2026-09-01", "requests": 10}],
        "comparison": [{"month": "2026-09", "requests": 10}],
        "categories": [{"category": "Other", "count": 3}],
    }


def test_untrusted_dimensions_and_nested_fields_cannot_escape():
    report = fixture()
    secret = "Person Name person@example.org 192.0.2.1 2001:db8::1 secret-token"
    for table in (
        "queries",
        "zeroQueries",
        "clients",
        "endpoints",
        "resources",
        "downloadBreakdown",
        "futureTable",
    ):
        report[table] = [{"query": secret, "context": {"geo": secret}, "count": 3}]
    report["totals"].update(ip=secret, views=secret, downloads={"email": secret})
    report["daily"][0]["userAgent"] = secret
    report["categories"].append({"category": secret, "count": 3})
    report["sources"] = {"overview": secret}
    before = copy.deepcopy(report)
    exported = public_report(report)
    assert secret not in str(exported)
    assert exported["totals"] == {"requests": 10}
    assert exported["daily"] == [{"date": "2026-09-01", "requests": 10}]
    assert exported["categories"] == [{"category": "Other", "count": 3}]
    assert report == before
    assert public_report(exported) == exported
    assert checksum({k: v for k, v in exported.items() if k != "revision"}) == exported["revision"]


def test_export_keeps_aggregate_counts_without_identifiers():
    exported = public_report(fixture())
    assert sum(row["requests"] for row in exported["daily"]) == exported["totals"]["requests"]
    assert exported["comparison"][0]["requests"] == 10
    assert exported["privacyVersion"] == "2"


def test_every_shipped_download_and_sidecar_obeys_privacy_contract():
    import csv
    import io
    import json
    import zipfile
    from pathlib import Path

    from app.services.analytics_reporting.public_export import PUBLIC_TABLES
    from scripts.export_analytics_snapshots import table_csv

    root = Path(__file__).resolve().parents[3] / "frontend/private-analytics-reports"
    manifest = json.loads((root / "manifest.json").read_text())
    expected = set()
    for entry in manifest["periods"]:
        folder = root / entry["id"] / entry["revision"]
        expected.add(folder / "tables.zip")
        with zipfile.ZipFile(folder / "tables.zip") as archive:
            report = json.loads(archive.read("report.json"))
            assert report == public_report(report)
            assert report["revision"] == entry["revision"]
            assert json.loads((folder / "report.json").read_text()) == report
            assert checksum(report) == entry["previewChecksum"]
            allowed = {"report.json"}
            for table, rows in report.items():
                if isinstance(rows, list) and all(isinstance(row, dict) for row in rows):
                    assert table in PUBLIC_TABLES or (table == "missingMonths" and not rows)
                    allowed.update((table + ".json", table + ".csv"))
                    assert json.loads(archive.read(table + ".json")) == rows
                    assert list(
                        csv.reader(io.StringIO(archive.read(table + ".csv").decode()))
                    ) == list(csv.reader(io.StringIO(table_csv(rows))))
            assert set(archive.namelist()) == allowed
    # A stale revision must not remain accessible through a previously shared URL.
    assert set(root.rglob("tables.zip")) == expected
    assert set(root.rglob("report.json")) == {p.with_name("report.json") for p in expected}


def test_runtime_refuses_old_revisions_and_identifier_tables(monkeypatch):
    import pytest
    from fastapi import HTTPException

    from app.api.v1.endpoint_modules import analytics_reports as api

    raw = fixture()
    monkeypatch.setattr(api, "read_document", lambda *args: raw)
    with pytest.raises(HTTPException) as blocked:
        api.report("2026-09", "0" * 64)
    assert blocked.value.status_code == 404
    safe = public_report(raw)
    monkeypatch.setattr(api, "read_document", lambda *args: safe)
    assert api.report("2026-09", safe["revision"]).status_code == 200
    for table in ("queries", "clients", "endpoints", "downloadBreakdown"):
        with pytest.raises(HTTPException) as blocked:
            api.download("2026-09", safe["revision"], table)
        assert blocked.value.status_code == 404
    assert api.download("2026-09", safe["revision"], "daily").status_code == 200


def test_runtime_publication_projects_before_storage(monkeypatch):
    import json
    from datetime import date

    from app.services.analytics_reporting import pipeline

    raw = fixture()
    raw["queries"] = [{"query": "person@example.org", "count": 3}]
    monkeypatch.setattr(pipeline, "build_report", lambda *args: raw)
    monkeypatch.setattr(pipeline, "periods", lambda *args: ["2026-09"])
    stored = []

    class Connection:
        def execute(self, statement, parameters=None):
            if parameters:
                stored.append(parameters)

    class Archive:
        def put(self, key, body):
            assert b"person@example.org" not in body
            if "/public/" in key:
                assert json.loads(body) == public_report(raw)

    pipeline.publish(Connection(), date(2026, 10, 1), [], [Archive()])
    assert "person@example.org" not in str(stored)
    documents = [json.loads(item["document"]) for item in stored if "document" in item]
    assert documents
    assert all(item["privacyVersion"] == "2" for item in documents)


def test_frontend_contract_fixture_is_an_actual_public_projection():
    import json
    from pathlib import Path

    fixture_path = Path(__file__).resolve().parents[1] / "fixtures/analytics/public-report.json"
    document = json.loads(fixture_path.read_text())
    assert public_report(document) == document
    assert "sourceCoverage" not in document
    assert "queries" not in document
