"""Previous-month counts from complete reports, never truncated ranking lists."""

from datetime import date


def popular_momentum(reports):
    result = {}
    for month in sorted(reports):
        if month == "all":
            continue
        current = date.fromisoformat(month + "-01")
        previous = date(current.year - (current.month == 1), (current.month - 2) % 12 + 1, 1)
        baseline = reports.get(previous.strftime("%Y-%m"))
        result[month] = (
            None
            if baseline is None
            else {
                "collections": {
                    row["id"]: row["views"] for row in baseline["collections"] if row["views"]
                },
                "downloads": {
                    row["id"]: row["downloads"] for row in baseline["resources"] if row["downloads"]
                },
                "outlinks": {
                    row["id"]: row["sourceClicks"]
                    for row in baseline["resources"]
                    if row["sourceClicks"]
                },
            }
        )
    return result
