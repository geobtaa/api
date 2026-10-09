#!/usr/bin/env python3
"""Build public dashboard snapshots from private, reconciled reporting archives."""

import argparse
import csv
import gzip
import io
import json
import re
import sys
import zipfile
from collections import defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.analytics_reporting.archive import validate_document  # noqa: E402
from app.services.analytics_reporting.reports import build_report  # noqa: E402
from app.services.analytics_reporting.storage import canonical, checksum  # noqa: E402

RANKINGS = {"queries", "zeroQueries", "resources", "outlinks", "downloads", "endpoints"}


def csv_cell(value):
    value = (
        json.dumps(value, sort_keys=True)
        if isinstance(value, (dict, list))
        else str(value if value is not None else "")
    )
    return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value


def table_csv(rows):
    stream = io.StringIO(newline="")
    fields = sorted({key for row in rows for key in row})
    writer = csv.writer(stream)
    writer.writerow(fields)
    writer.writerows([[csv_cell(row.get(key)) for key in fields] for row in rows])
    return stream.getvalue()


def preview(report):
    """Limit rendered rankings, never totals or full downloadable evidence."""
    result = dict(report)
    result["displayLimit"] = 100
    for key in RANKINGS:
        result[key] = report[key][:100]
    groups = defaultdict(list)
    for row in report["memberResources"]:
        groups[(row["grouping"], row["name"])].append(row)
    result["memberResources"] = []
    for rows in groups.values():
        chosen = {}
        for metric in ("views", "downloads", "sourceClicks", "impressions"):
            for row in sorted(rows, key=lambda r: (-r.get(metric, 0), r["id"]))[:10]:
                chosen[row["id"]] = row
        result["memberResources"].extend(chosen.values())
    return result


def zip_entry(archive, name, body):
    # Stable bytes when the same immutable report is regenerated.
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    archive.writestr(info, body)


def export(archives, through, output, selected):
    documents = []
    seen = set()
    for path in archives:
        document = json.loads(gzip.decompress(path.read_bytes()))
        digest = re.search(r"-([a-f0-9]{64})\.json\.gz$", path.name)
        if digest and checksum(document) != digest[1]:
            raise ValueError(f"Archive checksum mismatch: {path.name}")
        validate_document(document)
        if document["month"] in seen:
            raise ValueError("Supply exactly one archive revision per month")
        seen.add(document["month"])
        documents.append(document)
    output.mkdir(parents=True, exist_ok=True)
    manifest = {"schemaVersion": 1, "throughExclusive": str(through), "periods": []}
    for period in selected:
        report = build_report(period, through, documents)
        if report["missingMonths"]:
            raise ValueError(f"Missing source months for {period}")
        for metric in ("requests", "searches", "views", "downloads", "sourceClicks", "impressions"):
            total = report["totals"].get(metric)
            if (
                total is not None
                and sum(row.get(metric, 0) or 0 for row in report["daily"]) != total
            ):
                raise ValueError(f"Daily {metric} does not reconcile for {period}")
        directory = output / period / report["revision"]
        directory.mkdir(parents=True, exist_ok=True)
        compact = canonical(preview(report))
        (directory / "report.json").write_bytes(compact)
        with zipfile.ZipFile(directory / "tables.zip", "w", zipfile.ZIP_DEFLATED) as archive:
            zip_entry(archive, "report.json", canonical(report))
            for table, rows in report.items():
                if isinstance(rows, list) and all(isinstance(row, dict) for row in rows):
                    zip_entry(archive, f"{table}.json", canonical(rows))
                    zip_entry(archive, f"{table}.csv", table_csv(rows))
        manifest["periods"].append(
            {
                "id": period,
                "revision": report["revision"],
                "complete": report["complete"],
                "start": report["start"],
                "endExclusive": report["endExclusive"],
                "previewChecksum": checksum(json.loads(compact)),
            }
        )
        print(
            json.dumps(
                {
                    "period": period,
                    "totals": report["totals"],
                    "days": len(report["daily"]),
                    "complete": report["complete"],
                }
            ),
            flush=True,
        )
    manifest["latest"] = max(period for period in selected if period[0].isdigit())
    (output / "manifest.json").write_bytes(canonical(manifest))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archives", type=Path, nargs="+")
    parser.add_argument("--through", type=date.fromisoformat, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--period", action="append", required=True)
    args = parser.parse_args()
    export(args.archives, args.through, args.output, args.period)
