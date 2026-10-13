"""Stage and validate a complete local dashboard refresh from private archives."""

import argparse
import json
import shutil
import sys
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.export_analytics_design_data import run  # noqa: E402
from scripts.export_analytics_snapshots import export  # noqa: E402


def reporting_boundary(today=None):
    """Exclude the current, incomplete UTC calendar month."""
    return (today or datetime.now(timezone.utc).date()).replace(day=1)


def update(archives, supplemental, frontend, through):
    if through.day != 1 or through > reporting_boundary():
        raise ValueError("Through must be the first day of a completed reporting boundary")
    months = []
    cursor = date(2026, 7, 1)
    while cursor < through:
        months.append(cursor.strftime("%Y-%m"))
        cursor = date(cursor.year + (cursor.month == 12), cursor.month % 12 + 1, 1)
    if len(months) < 3:
        raise ValueError("Monthly refresh requires coverage through September 2026 or later")
    with tempfile.TemporaryDirectory(prefix="analytics-refresh-") as temp:
        stage = Path(temp)
        public, data = stage / "public", stage / "data"
        shutil.copytree(frontend / "src/data/analytics", data)
        export(archives, through, public, [*months, "all"])
        manifest = json.loads((public / "manifest.json").read_text())
        incomplete = [
            entry["id"]
            for entry in manifest["periods"]
            if entry["id"] in months[2:] and not entry["complete"]
        ]
        if incomplete:
            raise ValueError(f"Incomplete monthly source coverage: {incomplete}")
        snapshots = {}
        for month in months[2:]:
            run(archives, public, data, supplemental, month)
            snapshots[month] = json.loads((data / f"month-{month}.json").read_text())
        (data / "monthlySnapshots.json").write_text(
            json.dumps(snapshots, ensure_ascii=False) + "\n"
        )
        # Immutable report revisions are installed first; manifest switches last.
        destination = frontend / "private-analytics-reports"
        for month in [*months, "all"]:
            shutil.copytree(public / month, destination / month, dirs_exist_ok=True)
        names = [
            "monthlySnapshots.json",
            "memberLeadingContent.json",
            "memberCollectionViews.json",
            "popularHistory2026.json",
            "allTimeCurrent.json",
            "memberAllTimeCurrent.json",
            "outcomesCurrent.json",
            "collectionSearchesCurrent.json",
            "collectionViewsCurrent.json",
            "popularMomentumCurrent.json",
            "reliabilityEndpointsCurrent.json",
        ]
        for name in names:
            target = frontend / "src/data/analytics" / name
            pending = target.with_suffix(".json.pending")
            shutil.copyfile(data / name, pending)
            pending.replace(target)
        pending = destination / "manifest.json.pending"
        shutil.copyfile(public / "manifest.json", pending)
        pending.replace(destination / "manifest.json")
    print(f"Prepared {months[-1]} and All time. Run dashboard checks before publication.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archives", nargs="+", type=Path)
    parser.add_argument("--supplemental", type=Path, required=True)
    parser.add_argument("--frontend", type=Path, default=Path("frontend"))
    parser.add_argument("--through", type=date.fromisoformat, default=reporting_boundary())
    args = parser.parse_args()
    update(args.archives, args.supplemental, args.frontend, args.through)
