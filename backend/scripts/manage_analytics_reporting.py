#!/usr/bin/env python3
"""Local reporting lifecycle CLI. Deployment and recovery runbooks are restricted."""

import argparse
import gzip
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from app.services.analytics_reporting.archive import (  # noqa: E402
    configured_archives,
    restore,
)
from app.services.analytics_reporting.contract import SOURCES, START  # noqa: E402
from app.services.analytics_reporting.pipeline import import_available_history, run  # noqa: E402
from app.services.analytics_reporting.storage import canonical, checksum, install  # noqa: E402
from db.migrations.analytics_storage import analytics_storage_engine  # noqa: E402


def archive_legacy(directory, archives):
    """Save original published inputs byte-for-byte; never claim full raw coverage."""
    files = sorted(p for p in directory.iterdir() if p.suffix in (".ts", ".json"))
    if not files:
        raise ValueError("No legacy analytics snapshots")
    manifest = {
        "schemaVersion": 1,
        "kind": "legacy-snapshots",
        "completeInputs": False,
        "files": [],
    }
    import hashlib

    for path in files:
        body = path.read_bytes()
        digest = hashlib.sha256(body).hexdigest()
        key = f"analytics/legacy/{digest}/{path.name}"
        for archive in archives:
            archive.put(key, body)
        manifest["files"].append({"name": path.name, "key": key, "sha256": digest})
    for archive in archives:
        archive.put(f"analytics/legacy/manifests/{checksum(manifest)}.json", canonical(manifest))
    return manifest


def verify_baselines(conn, expected):
    """Expected source counts must come from independently preserved evidence."""
    from app.services.analytics_reporting.storage import drain

    while drain(conn):
        pass
    for period, sources in expected.items():
        month = date.fromisoformat(period + "-01")
        if set(sources) != set(SOURCES):
            raise ValueError("A completeness baseline must cover all four sources")
        for source, count in sources.items():
            observed = conn.execute(
                text("""SELECT count(*) FROM analytics_reporting_outbox
                WHERE source_month=:month AND source=:source AND processed_at IS NOT NULL"""),
                {"month": month, "source": source},
            ).scalar()
            if count is None:
                continue
            if not isinstance(count, int) or count < 0 or observed != count:
                raise ValueError(f"Baseline mismatch for {period} {source}: {observed} != {count}")
        conn.execute(
            text("""UPDATE analytics_reporting_months
            SET coverage=coverage || CAST(:coverage AS jsonb),generation=generation+1
            WHERE month=:month"""),
            {
                "month": month,
                "coverage": json.dumps(
                    {
                        "complete": all(n is not None for n in sources.values()),
                        "sources": sources,
                        "basis": "independent historical source-count baseline",
                    }
                ),
            },
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=(
            "install",
            "backfill",
            "publish",
            "health",
            "restore",
            "import-legacy",
            "verify-baselines",
            "export-readonly",
        ),
    )
    parser.add_argument("--start", type=date.fromisoformat, default=START)
    parser.add_argument("--end", type=date.fromisoformat, default=date.today().replace(day=1))
    parser.add_argument("--input", type=Path)
    parser.add_argument("--checksum")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--legacy", type=Path)
    args = parser.parse_args()
    if args.start.day != 1 or args.end.day != 1 or args.end <= args.start:
        parser.error("Bounds must be increasing month starts; end is exclusive")
    engine = analytics_storage_engine()
    try:
        if args.action == "export-readonly":
            from app.services.analytics_reporting.migration import export_readonly

            if args.input is None or args.output is None:
                parser.error("export-readonly requires --input baselines and --output directory")
            baselines = json.loads(args.input.read_text())
            legacy = json.loads(args.legacy.read_text()) if args.legacy else {}
            args.output.mkdir(parents=True, exist_ok=True)
            with engine.begin() as conn:
                conn.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
                conn.execute(text("SET LOCAL TIME ZONE 'UTC'"))
                for period, expected in baselines.items():
                    month = date.fromisoformat(period + "-01")
                    if not args.start <= month < args.end:
                        continue
                    document = export_readonly(conn, month, expected, legacy.get(period))
                    digest = checksum(document)
                    destination = args.output / f"{period}-{digest}.json.gz"
                    with destination.open("xb") as stream:
                        stream.write(gzip.compress(canonical(document), mtime=0))
                    print(json.dumps({"period": period, "checksum": digest}))
            return
        if args.action == "publish":
            print(json.dumps(run(engine)))
            return
        if args.action == "import-legacy":
            if args.input is None:
                parser.error("import-legacy requires --input directory")
            print(json.dumps(archive_legacy(args.input, configured_archives())))
            return
        with engine.begin() as conn:
            if args.action == "install":
                install(conn)
            elif args.action == "backfill":
                print(import_available_history(conn, args.start, args.end))
            elif args.action == "verify-baselines":
                if args.input is None:
                    parser.error("verify-baselines requires --input JSON")
                verify_baselines(conn, json.loads(args.input.read_text()))
                if args.legacy:
                    for period, snapshot in json.loads(args.legacy.read_text()).items():
                        conn.execute(
                            text("""UPDATE analytics_reporting_months
                            SET legacy=CAST(:legacy AS jsonb),generation=generation+1
                            WHERE month=:month"""),
                            {
                                "month": date.fromisoformat(period + "-01"),
                                "legacy": canonical(snapshot).decode(),
                            },
                        )
            elif args.action == "restore":
                if args.input is None or args.checksum is None:
                    parser.error("restore requires --input and --checksum")
                body = (
                    gzip.decompress(args.input.read_bytes())
                    if args.input.suffix == ".gz"
                    else args.input.read_bytes()
                )
                restore(conn, json.loads(body), args.checksum)
            else:
                records = conn.execute(text("SELECT * FROM analytics_reporting_health")).mappings()
                print(json.dumps([dict(r) for r in records], default=str))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
