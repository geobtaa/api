"""Screened, reproducible evidence for aggregate reports, never raw audit records."""

from collections import Counter
from datetime import date, datetime

from .archive import validate_document
from .contract import SOURCES
from .public_export import public_report
from .reports import build_report
from .storage import checksum

ADDITIVE = ("requests", "searches", "views", "downloads", "sourceClicks", "impressions")
DEFINITIONS = {
    "requests": "Recorded API requests, including automated traffic and probes.",
    "searches": "Recorded search events; repeated searches count separately.",
    "views": "Recorded resource-view events, not all website pageviews or unique people.",
    "downloads": "Recorded download-link clicks, not confirmed file transfers.",
    "sourceClicks": "Recorded source-site link clicks, not confirmed visits or transfers.",
    "impressions": "Recorded appearances of resources in search results.",
    "trackedVisits": "An estimate from merged tab-scoped token sketches; not unique people. "
    "Daily estimates must not be added to obtain a period estimate.",
    "latency": "Response times for recorded API requests. Percentiles cannot be added or "
    "averaged across months; historical values may come from preserved baselines.",
}
LIMITATIONS = [
    "Reconciliation establishes consistency of recorded data, "
    + "not capture of every real-world interaction.",
    "Coverage is the report's recorded declaration, not an independent certification.",
    "Independent baseline documents and deployed archive durability "
    + "were not verified by this packet.",
    "This packet covers the aggregate report only. Detailed rankings, member attribution, "
    + "client classifications and supplemental dashboard data are outside its verification scope.",
    "Catalog attribution uses captured metadata, which need not represent month-end inventory.",
    "Checksums detect changed content; they are not signatures or independent attestations.",
]


def build_evidence(report, documents=None):
    """Never turn missing evidence into a passed check or silently repair a report."""
    screened = public_report(report)
    if report != screened:
        raise ValueError("Evidence requires an unchanged, screened report with a valid revision")
    dates = [row["date"] for row in report["daily"]]
    if len(dates) != len(set(dates)) or any(
        not report["start"] <= day < report["endExclusive"] for day in dates
    ):
        raise ValueError("Daily dates must be unique and inside the report period")
    expected_days = (
        date.fromisoformat(report["endExclusive"]) - date.fromisoformat(report["start"])
    ).days
    checks = []
    for metric in ADDITIVE:
        total = report["totals"].get(metric)
        values = [row.get(metric) for row in report["daily"]]
        # Sparse daily metrics mean zero in the report contract; explicit null is unavailable.
        unavailable = any(metric in row and row[metric] is None for row in report["daily"])
        daily = sum(value or 0 for value in values)
        status = "unavailable" if total is None or unavailable or not values else "passed"
        if status == "passed" and total != daily:
            raise ValueError(f"Daily {metric} does not reconcile for {report['period']}")
        checks.append({"metric": metric, "reported": total, "dailySum": daily, "status": status})
    inputs = []
    if documents is not None:
        if len({d["month"] for d in documents}) != len(documents):
            raise ValueError("Supply exactly one archive revision per month")
        for document in documents:
            validate_document(document)
        regenerated = public_report(
            build_report(report["period"], date.fromisoformat(report["endExclusive"]), documents)
        )
        if regenerated != report:
            raise ValueError("Preserved inputs do not reproduce this report revision")
        for document in sorted(documents, key=lambda d: d["month"]):
            observed = Counter(row["source"] for row in document["receipts"])
            sources = []
            for source in sorted(SOURCES):
                expected = document["coverage"].get("sources", {}).get(source)
                if expected is not None and (type(expected) is not int or expected < 0):
                    raise ValueError("Invalid declared source baseline")
                if expected is not None and expected != observed[source]:
                    raise ValueError(
                        "Processing receipts do not match the declared source baseline"
                    )
                sources.append(
                    {
                        "source": source,
                        "processedRecords": observed[source],
                        "declaredBaseline": expected,
                        "status": "matched-declared-baseline"
                        if expected is not None
                        else "unavailable",
                    }
                )
            captured = document.get("catalogCapturedAt")
            # Only typed dates and hashes leave the archive; no paths, queries or source IDs.
            if captured is not None:
                captured = datetime.fromisoformat(str(captured)).isoformat()
            inputs.append(
                {
                    "month": date.fromisoformat(document["month"]).strftime("%Y-%m"),
                    "archiveChecksum": checksum(document),
                    "scope": "report-period"
                    if report["start"] <= document["month"] < report["endExclusive"]
                    else "comparison-only",
                    "catalogCapturedAt": captured,
                    "receiptReconciliation": "passed",
                    "includesPreservedLegacyAggregates": bool(document.get("legacy")),
                    "sources": sources,
                }
            )
    result = {
        "schemaVersion": 1,
        "evidenceVersion": "1",
        "period": report["period"],
        "start": report["start"],
        "endExclusive": report["endExclusive"],
        "reportRevision": report["revision"],
        "reportChecksum": checksum(report),
        "calculationVersion": report["calculationVersion"],
        "privacyVersion": report["privacyVersion"],
        "coverage": {
            "declaredComplete": report["complete"],
            "missingMonths": report["missingMonths"],
        },
        "verification": {
            "reportIntegrity": "passed",
            "dailyCalendar": "passed" if len(dates) == expected_days else "incomplete",
            "preservedInputReplay": "passed" if documents is not None else "not-verified",
            "independentBaselineEvidence": "not-verified",
            "deployedPreservation": "not-verified",
        },
        "reconciliation": checks,
        "inputs": inputs,
        "definitions": DEFINITIONS,
        "trackedVisits": report["trackedVisits"],
        "limitations": LIMITATIONS,
    }
    result["evidenceChecksum"] = checksum(result)
    return result


def evidence_text(evidence):
    """Human-readable companion generated from exactly the same checks as the JSON."""
    lines = [
        f"Report evidence: {evidence['period']}",
        f"UTC interval: {evidence['start']} inclusive to {evidence['endExclusive']} exclusive",
        f"Report revision: {evidence['reportRevision']}",
        f"Report checksum: {evidence['reportChecksum']}",
        f"Evidence checksum: {evidence['evidenceChecksum']}",
        f"Calculation version: {evidence['calculationVersion']}",
        "Declared source coverage: "
        + ("complete" if evidence["coverage"]["declaredComplete"] else "incomplete"),
        "",
        "Verification:",
    ]
    lines.extend(f"- {name}: {status}" for name, status in evidence["verification"].items())
    lines.extend(["", "Daily-to-period reconciliation:"])
    lines.extend(
        f"- {row['metric']}: reported={row['reported']}; "
        f"daily sum={row['dailySum']}; {row['status']}"
        for row in evidence["reconciliation"]
    )
    lines.extend(["", "Definitions:"])
    lines.extend(f"- {key}: {value}" for key, value in evidence["definitions"].items())
    lines.extend(["", "Limitations:", *[f"- {value}" for value in evidence["limitations"]]])
    lines.extend(
        [
            "",
            "Input archive hashes, catalog capture dates, and source-count checks (when supplied) "
            + "are in evidence.json. Original receipts remain private.",
            "Checksums use SHA-256 over UTF-8 JSON with sorted keys and compact separators. "
            + "For the report revision omit revision; "
            + "for the evidence checksum omit evidenceChecksum. "
            + "The report checksum includes revision. This packet has no external signature.",
        ]
    )
    return "\n".join(lines) + "\n"
