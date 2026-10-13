import copy
import json
import zipfile
from datetime import date
from pathlib import Path

import pytest

from app.services.analytics_reporting.contract import SOURCES
from app.services.analytics_reporting.evidence import build_evidence
from app.services.analytics_reporting.public_export import public_report
from app.services.analytics_reporting.reports import build_report
from app.services.analytics_reporting.storage import checksum
from scripts.export_analytics_evidence import export_evidence
from scripts.export_analytics_snapshots import write_evidence


@pytest.fixture
def report():
    return json.loads(
        (Path(__file__).parents[1] / "fixtures/analytics/public-report.json").read_text()
    )


def archive():
    dimensions = {
        "source": "analytics_api_usage_logs",
        "client": "PRIVATE-CLIENT",
        "channel": "api",
        "endpoint": "/PRIVATE-ENDPOINT",
        "method": "GET",
        "status": 200,
    }
    key = checksum(dimensions)
    metrics = {"count": 1, "durationSum": 10, "durationCount": 1, "latency:10": 1}
    return {
        "schemaVersion": 1,
        "month": "2026-09-01",
        "coverage": {
            "complete": True,
            "sources": {s: int(s == "analytics_api_usage_logs") for s in SOURCES},
        },
        "catalog": {},
        "catalogCapturedAt": "2026-10-01T12:00:00+00:00",
        "visits": [],
        "daily": [
            {
                "metric_date": "2026-09-01",
                "dimension_key": key,
                "dimensions": dimensions,
                "metrics": metrics,
            }
        ],
        "receipts": [
            {
                "source": "analytics_api_usage_logs",
                "source_id": "PRIVATE-ID",
                "fingerprint": "PRIVATE-FINGERPRINT",
                "metric_date": "2026-09-01",
                "dimension_key": key,
                "contribution": dict(metrics),
            }
        ],
    }


def test_report_only_evidence_does_not_claim_source_or_external_verification(report):
    packet = build_evidence(report)
    assert packet["verification"]["preservedInputReplay"] == "not-verified"
    assert packet["verification"]["independentBaselineEvidence"] == "not-verified"
    assert packet["inputs"] == []
    assert all(row["status"] == "passed" for row in packet["reconciliation"])
    assert "trackedVisits" not in [r["metric"] for r in packet["reconciliation"]]
    assert packet["evidenceChecksum"] == checksum(
        {k: v for k, v in packet.items() if k != "evidenceChecksum"}
    )


def test_rejects_tampered_report_and_resealed_arithmetic_error(report):
    report["totals"]["searches"] += 1
    with pytest.raises(ValueError, match="valid revision"):
        build_evidence(report)
    with pytest.raises(ValueError, match="Daily searches"):
        build_evidence(public_report(report))


def test_null_metrics_are_unavailable_not_verified_zero(report):
    report["totals"]["requests"] = None
    packet = build_evidence(public_report(report))
    assert (
        next(r for r in packet["reconciliation"] if r["metric"] == "requests")["status"]
        == "unavailable"
    )


def test_source_receipts_replay_and_privacy():
    document = archive()
    report = public_report(build_report("2026-09", date(2026, 10, 1), [document]))
    packet = build_evidence(report, [document])
    assert packet["verification"]["preservedInputReplay"] == "passed"
    assert packet["inputs"][0]["archiveChecksum"] == checksum(document)
    assert packet["inputs"][0]["sources"][0]["processedRecords"] == 1
    assert "PRIVATE-" not in json.dumps(packet)
    broken = copy.deepcopy(document)
    broken["receipts"][0]["contribution"]["count"] = 2
    with pytest.raises(ValueError, match="do not reconcile"):
        build_evidence(report, [broken])
    document["coverage"]["sources"]["analytics_api_usage_logs"] = 2
    with pytest.raises(ValueError, match="declared source baseline"):
        build_evidence(report, [document])


def test_rejects_different_inputs_and_duplicate_months():
    document = archive()
    report = public_report(build_report("2026-09", date(2026, 10, 1), [document]))
    with pytest.raises(ValueError, match="one archive revision"):
        build_evidence(report, [document, document])
    document["daily"] = []
    document["receipts"] = []
    with pytest.raises(ValueError, match="do not reproduce"):
        build_evidence(report, [document])


def test_deterministic_packet_contains_exact_report_and_readable_results(report, tmp_path):
    pointer = write_evidence(report, tmp_path)
    path = tmp_path / f"evidence-{pointer['checksum']}.zip"
    first = path.read_bytes()
    write_evidence(report, tmp_path)
    assert path.read_bytes() == first
    with zipfile.ZipFile(path) as packet:
        assert json.loads(packet.read("report.json")) == report
        assert b"not-verified" in packet.read("README.txt")
        assert "daily.csv" in packet.namelist()


def test_published_packets_match_manifest_reports_and_all_six_metrics():
    directory = Path(__file__).resolve().parents[3] / "frontend/private-analytics-reports"
    manifest = json.loads((directory / "manifest.json").read_text())
    for entry in manifest["periods"]:
        folder = directory / entry["id"] / entry["revision"]
        report = json.loads((folder / "report.json").read_text())
        name = f"evidence-{entry['evidence']['checksum']}"
        packet = json.loads((folder / f"{name}.json").read_text())
        assert packet["reportChecksum"] == checksum(report) == entry["previewChecksum"]
        assert packet["reportRevision"] == entry["revision"]
        assert packet["coverage"]["declaredComplete"] == entry["complete"]
        assert packet["evidenceChecksum"] == checksum(
            {k: v for k, v in packet.items() if k != "evidenceChecksum"}
        )
        assert packet["reconciliation"] == build_evidence(report)["reconciliation"]
        with zipfile.ZipFile(folder / f"{name}.zip") as bundle:
            assert json.loads(bundle.read("report.json")) == report
            assert json.loads(bundle.read("evidence.json")) == packet
    assert len(manifest["periods"]) >= 4


def test_manifest_mismatch_leaves_published_manifest_unchanged(report, tmp_path):
    folder = tmp_path / report["period"] / report["revision"]
    folder.mkdir(parents=True)
    (folder / "report.json").write_text(json.dumps(report))
    manifest = {
        "periods": [
            {"id": report["period"], "revision": report["revision"], "previewChecksum": "wrong"}
        ]
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="Manifest"):
        export_evidence(tmp_path)
    assert json.loads(path.read_text()) == manifest


def test_daily_calendar_rejects_duplicates_and_out_of_period_dates(report):
    report["daily"][1]["date"] = report["daily"][0]["date"]
    with pytest.raises(ValueError, match="Daily dates"):
        build_evidence(public_report(report))
    report["daily"][1]["date"] = report["endExclusive"]
    with pytest.raises(ValueError, match="Daily dates"):
        build_evidence(public_report(report))


def test_comparison_input_hashes_are_included():
    september = archive()
    august = {
        **archive(),
        "month": "2026-08-01",
        "daily": [],
        "receipts": [],
        "coverage": {"complete": True, "sources": {s: 0 for s in SOURCES}},
    }
    report = public_report(build_report("2026-09", date(2026, 10, 1), [august, september]))
    packet = build_evidence(report, [august, september])
    assert packet["inputs"][0]["scope"] == "comparison-only"
    assert packet["inputs"][0]["archiveChecksum"] == checksum(august)
    assert packet["inputs"][1]["scope"] == "report-period"


def test_snapshot_export_installs_reproducible_evidence_and_detects_tampering(tmp_path):
    import gzip

    from app.services.analytics_reporting.storage import canonical
    from scripts.export_analytics_snapshots import export

    document = archive()
    source = tmp_path / f"2026-09-{checksum(document)}.json.gz"
    source.write_bytes(gzip.compress(canonical(document)))
    output = tmp_path / "published"
    export([source], date(2026, 10, 1), output, ["2026-09"])
    export_evidence(output, check=True, archives=[source])
    entry = json.loads((output / "manifest.json").read_text())["periods"][0]
    path = (
        output / entry["id"] / entry["revision"] / f"evidence-{entry['evidence']['checksum']}.json"
    )
    path.write_text("{}")
    with pytest.raises(ValueError, match="differs from reproducible"):
        export_evidence(output, check=True, archives=[source])
