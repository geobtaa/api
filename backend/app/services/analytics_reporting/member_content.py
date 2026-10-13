"""Leading member content from complete preserved resource aggregates."""

from collections import defaultdict

from .pipeline import CODE_LABELS


def member_content(report, viewed_limit=50, downloaded_limit=25):
    groups = defaultdict(dict)
    codes = {name: code for code, name in CODE_LABELS.items()}
    for row in report["memberResources"]:
        if row["grouping"] != "code" or row["name"] not in codes:
            continue
        item = {key: row[key] for key in ("id", "title", "views", "downloads")}
        groups[codes[row["name"]]][item["id"]] = item
        # A resource can appear in multiple contribution streams. Count it once.
        groups["all"][item["id"]] = item
    return {
        code: {
            label: sorted(
                [row for row in groups[code].values() if row[metric] > 0],
                key=lambda row: (-row[metric], row["id"]),
            )[: viewed_limit if metric == "views" else downloaded_limit]
            for label, metric in (("viewed", "views"), ("downloaded", "downloads"))
        }
        for code in ["all", *CODE_LABELS]
    }
