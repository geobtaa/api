import argparse
import collections
import hashlib
import json
from pathlib import Path

parser = argparse.ArgumentParser(
    description="Project preserved member aggregates for the shared report UI."
)
parser.add_argument("source", type=Path)
parser.add_argument("--output", required=True, type=Path)
args = parser.parse_args()
source = args.source
p = json.loads(source.read_text())
daily = collections.defaultdict(list)
resources = collections.defaultdict(list)
for r in p["memberDaily"]:
    daily[(r["grouping"], r["name"])].append({k: r[k] for k in ("date", "views", "downloads")})
for r in p["memberResources"]:
    resources[(r["grouping"], r["name"])].append(
        {k: r[k] for k in ("id", "title", "views", "downloads")}
    )
groups = []
for row in p["members"]:
    key = (row["grouping"], row["name"])
    groups.append(
        {
            **{
                key: row[key]
                for key in (
                    "grouping",
                    "name",
                    "inventory",
                    "activeResources",
                    "views",
                    "downloads",
                    "sourceClicks",
                    "impressions",
                    "resultOpens",
                )
            },
            "daily": sorted(daily[key], key=lambda r: r["date"]),
            "topViews": sorted(
                [r for r in resources[key] if r["views"]], key=lambda r: (-r["views"], r["id"])
            )[:3],
            "topDownloads": sorted(
                [r for r in resources[key] if r["downloads"]],
                key=lambda r: (-r["downloads"], r["id"]),
            )[:3],
        }
    )
result = {
    "start": p["start"],
    "endExclusive": p["endExclusive"],
    "catalogCapturedAt": max(c["catalogCapturedAt"] for c in p["coverage"]),
    "sourceSha256": hashlib.sha256(source.read_bytes()).hexdigest(),
    "groups": groups,
    "totals": {k: p["totals"][k] for k in ["views", "downloads", "impressions", "sourceClicks"]},
}
args.output.write_text(json.dumps(result, indent=2) + "\n")
