"""Adapt preserved reports to the established dashboard's presentation data."""

import argparse
import gzip
import json
import sys
import zipfile
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.analytics_reporting.archive import validate_document  # noqa: E402
from app.services.analytics_reporting.collection_searches import collection_searches  # noqa: E402
from app.services.analytics_reporting.metadata import (  # noqa: E402
    content_metadata,
    content_providers,
)
from app.services.analytics_reporting.storage import checksum  # noqa: E402

COLORS = ["#003C5B", "#1E40AF", "#2563EB", "#3B82F6", "#60A5FA", "#93C5FD", "#BFDBFE"]


def counts(row):
    return dict(
        catalogRecords=row["inventory"],
        activeResources=row["activeResources"],
        resourceViews=row["views"],
        downloadClicks=row["downloads"],
        sourceClicks=row["sourceClicks"],
        impressions=row["impressions"],
    )


def member_report(report):
    daily, resources = defaultdict(list), defaultdict(list)
    for row in report["memberDaily"]:
        daily[(row["grouping"], row["name"])].append(
            {k: row[k] for k in ["date", "views", "downloads"]}
        )
    for row in report["memberResources"]:
        resources[(row["grouping"], row["name"])].append(
            {k: row[k] for k in ["id", "title", "views", "downloads"]}
        )
    groups = []
    for row in report["members"]:
        key = (row["grouping"], row["name"])
        groups.append(
            {
                **row,
                "daily": sorted(daily[key], key=lambda x: x["date"]),
                "topViews": sorted(
                    [r for r in resources[key] if r["views"]], key=lambda r: (-r["views"], r["id"])
                )[:3],
                "topDownloads": sorted(
                    [r for r in resources[key] if r["downloads"]],
                    key=lambda r: (-r["downloads"], r["id"]),
                )[:3],
            }
        )
    return dict(
        start=report["start"],
        endExclusive=report["endExclusive"],
        catalogCapturedAt=max(r["catalogCapturedAt"] for r in report["coverage"]),
        sourceSha256=report["revision"],
        groups=groups,
        totals={
            k: report["totals"][k] for k in ["views", "downloads", "impressions", "sourceClicks"]
        },
    )


def search_details(documents):
    terms, classes = Counter(), Counter()
    with_query = zero_with_query = positive = 0
    for doc in documents:
        for row in doc["daily"]:
            dim, metrics = row["dimensions"], row["metrics"]
            if dim["source"] != "analytics_searches":
                continue
            if (dim.get("query") or "").strip():
                terms[dim["query"].strip()] += metrics["count"]
                with_query += metrics["count"]
                zero_with_query += metrics.get("zeroResults", 0)
            positive += sum(
                n
                for key, n in metrics.items()
                if key.startswith("zeroResultTotal:") and float(key.split(":")[1]) > 0
            )
            used = set()
            for key, values in dim.get("context", {}).items():
                if key.startswith("include_filters[gbl_resourceClass_sm]"):
                    used.update(values)
            for value in used:
                classes[value] += metrics["count"]
    return dict(
        withQuery=with_query,
        distinctQueries=len(terms),
        zeroWithQuery=zero_with_query,
        zeroResultsWithPositiveTotal=positive,
        resourceClassFilters=[
            dict(label=k, count=n, color=COLORS[i % len(COLORS)])
            for i, (k, n) in enumerate(classes.most_common())
        ],
    )


def endpoint_rows(rows):
    result = defaultdict(Counter)
    for row in rows:
        result[row["endpoint"]]["requests"] += row["count"]
        if (row["status"] or 0) >= 500:
            result[row["endpoint"]]["errors"] += row["count"]
    return [
        dict(label=k, requests=v["requests"], errors=v["errors"])
        for k, v in sorted(result.items(), key=lambda x: -x[1]["requests"])
    ]


def outcomes(report, details):
    def ranking(key, metric):
        return [
            dict(
                id=r["id"],
                title=r["title"],
                provider=", ".join(r.get("provider") or []),
                clicks=r[metric],
            )
            for r in report[key][:50]
        ]

    contexts = {}
    withheld = {}

    def parameter(context, key):
        value = context["constraints"].get(key)
        value = value[0] if isinstance(value, list) and value else value
        if key in ("page", "total_pages") and value is not None:
            return int(value)
        return value

    for row in report["zeroQueries"]:
        if row["query"] == "Suppressed queries":
            continue
        withheld[row["query"]] = row.get("withheldContextCount", 0)
        contexts[row["query"]] = [
            dict(
                constraints=c["constraints"],
                page=parameter(c, "page"),
                view=parameter(c, "view"),
                sort=parameter(c, "sort"),
                searchField=parameter(c, "search_field"),
                resultsCount=int(total),
                totalPages=parameter(c, "total_pages"),
                count=n,
            )
            for c in row["context"]
            for total, n in c["resultTotals"].items()
        ]
    return dict(
        start=report["start"],
        endExclusive=report["endExclusive"],
        searches=report["totals"]["searches"],
        totals=dict(
            events=report["totals"]["events"],
            sources=report["totals"]["sourceClicks"],
            downloads=report["totals"]["downloads"],
            views=report["totals"]["views"],
            pageViews=0,
        ),
        audience=dict(
            trackedVisits=report["trackedVisits"]["value"],
            estimated=True,
            recordsWithoutToken=report["totals"]["recordsWithoutToken"],
            activityRecords=report["totals"]["searches"] + report["totals"]["events"],
        ),
        clients=[
            dict(client=r["client"], channel=r["channel"], records=r["searches"] + r["events"])
            for r in report["clients"]
        ],
        daily=[
            dict(
                day=r["date"],
                visits=r["visits"],
                searches=r["searches"],
                sources=r["sourceClicks"],
                downloads=r["downloads"],
                views=r["views"],
            )
            for r in report["daily"]
        ],
        outlinks=ranking("outlinks", "sourceClicks"),
        downloads=ranking("downloads", "downloads"),
        zeroResultContexts=contexts,
        withheldSearchContexts=withheld,
        zeroResultsWithPositiveTotal=details["zeroResultsWithPositiveTotal"],
        zeroResults=report["totals"]["zeroResults"],
    )


def popular_content(document):
    """Rank all preserved monthly event rows before limiting the presentation."""
    activity = defaultdict(Counter)
    for row in document["daily"]:
        dim = row["dimensions"]
        identifier = dim.get("resource")
        if dim["source"] != "analytics_events" or not identifier:
            continue
        n = row["metrics"]["count"]
        activity[identifier][dim["event"]] += n
        activity[identifier]["events"] += n
        activity[identifier]["first" if row["metric_date"][8:10] <= "15" else "second"] += n

    def metadata(identifier):
        record = content_metadata(document["catalog"].get(identifier, {}))
        attrs = record.get("attributes") or {}

        def labels(value):
            return ", ".join(value) if isinstance(value, list) else value or ""

        return dict(
            id=identifier,
            title=record.get("title") or identifier,
            provider=", ".join(content_providers(record)),
            resourceClass=labels(attrs.get("resourceClasses")),
            resourceType=labels(attrs.get("resourceTypes")),
            formatLabel=labels(attrs.get("format")),
        )

    def ranked(metric):
        return sorted(
            [key for key, counts in activity.items() if counts[metric]],
            key=lambda key: (-activity[key][metric], key),
        )

    return dict(
        topResources=[
            dict(
                **metadata(key),
                views=activity[key]["resource_view"],
                actions=activity[key]["events"] - activity[key]["resource_view"],
                firstHalfEvents=activity[key]["first"],
                secondHalfEvents=activity[key]["second"],
            )
            for key in ranked("resource_view")[:50]
        ],
        topCollections=collection_searches([document])[:50],
        topDownloads=[
            dict(
                **metadata(key),
                clicks=activity[key]["download_click"],
                engagedVisits=None,
            )
            for key in ranked("download_click")[:50]
        ],
        downloadResources=len(ranked("download_click")),
    )


def run(archives, public, output, supplemental, period=None):
    docs = []
    for path in archives:
        doc = json.loads(gzip.decompress(path.read_bytes()))
        validate_document(doc)
        if path.name.split("-", 2)[-1].split(".")[0] != checksum(doc):
            raise ValueError("Archive checksum mismatch")
        docs.append(doc)
    docs.sort(key=lambda d: d["month"])
    months = [d["month"][:7] for d in docs]
    expected = []
    cursor = date(2026, 7, 1)
    end = date.fromisoformat(docs[-1]["month"])
    while cursor <= end:
        expected.append(cursor.strftime("%Y-%m"))
        cursor = date(cursor.year + (cursor.month == 12), cursor.month % 12 + 1, 1)
    if months != expected or len(months) < 3:
        raise ValueError("Expected one verified archive per month since July 2026")
    period = period or months[-1]
    if period not in months[2:]:
        raise ValueError("Projection period must be a supplied month from September 2026 onward")
    manifest = json.loads((public / "manifest.json").read_text())
    reports = {}
    for entry in manifest["periods"]:
        with zipfile.ZipFile(public / entry["id"] / entry["revision"] / "tables.zip") as z:
            report = json.loads(z.read("report.json"))
        unsigned = {k: v for k, v in report.items() if k != "revision"}
        if checksum(unsigned) != entry["revision"]:
            raise ValueError("Public report checksum mismatch")
        reports[entry["id"]] = report
    sep = reports[period]
    all_report = reports["all"]
    doc = docs[months.index(period)]
    daily_extra = defaultdict(Counter)
    for row in doc["daily"]:
        source = row["dimensions"]["source"]
        if source == "analytics_events":
            daily_extra[row["metric_date"]]["events"] += row["metrics"]["count"]
        if source == "analytics_searches":
            daily_extra[row["metric_date"]]["zeroResults"] += row["metrics"].get("zeroResults", 0)
    for row in sep["daily"]:
        row.update(daily_extra[row["date"]])
    details = search_details([doc])
    all_details = search_details(docs)
    verified = json.loads(supplemental.read_text().splitlines()[-1])
    for verified_period, result in [(period, details), ("all", all_details)]:
        if verified[verified_period]["searches"] != reports[verified_period]["totals"]["searches"]:
            raise ValueError("Supplemental search counts do not reconcile")
        result.update(
            withQuery=verified[verified_period]["with_query"],
            distinctQueries=verified[verified_period]["distinct_queries"],
            zeroWithQuery=verified[verified_period]["zero_with_query"],
        )
    member = member_report(sep)
    dates = [r["date"] for r in sep["daily"]]
    providers = [r for r in member["groups"] if r["grouping"] == "provider"]
    provider = dict(
        month=period,
        catalogSnapshotDate=doc["catalogCapturedAt"][:10],
        exportedAt=doc["catalogCapturedAt"],
        totals={k: sum(counts(r)[k] for r in providers) for k in counts(providers[0])},
        groups=[
            dict(
                **counts(r),
                id=r["name"],
                provider=r["name"],
                daily=[
                    dict(
                        day=i + 1,
                        views=next((v["views"] for v in r["daily"] if v["date"] == d), 0),
                        downloads=next((v["downloads"] for v in r["daily"] if v["date"] == d), 0),
                    )
                    for i, d in enumerate(dates)
                ],
                topViews=r["topViews"],
                topDownloads=r["topDownloads"],
            )
            for r in providers
        ],
        codeCoverage=[
            dict(**counts(r), label=r["name"]) for r in member["groups"] if r["grouping"] == "code"
        ],
    )
    latency = Counter()
    events = defaultdict(Counter)
    peak = Counter()
    mix = Counter()
    surfaces = Counter()
    clients = defaultdict(Counter)
    peak_day = max(sep["daily"], key=lambda r: r["requests"])["date"]
    for row in doc["daily"]:
        dim, m = row["dimensions"], row["metrics"]
        n = m["count"]
        source = dim["source"]
        if source == "analytics_events":
            events[dim.get("resource")][
                "first" if row["metric_date"][8:10] <= "15" else "second"
            ] += n
            events[dim.get("resource")]["events"] += n
        if source == "analytics_api_usage_logs":
            for k, v in m.items():
                if k.startswith("latency:"):
                    latency[int(k.split(":")[1])] += v
            path = dim.get("endpoint", "")
            family = (
                "API docs"
                if path == "/api/docs"
                else "Access checks"
                if path == "/api/v1/turnstile/status"
                else "Analytics capture"
                if path == "/api/v1/analytics/events"
                else "Everything else"
            )
            mix[family] += n
            surface = (
                "MCP endpoints"
                if "/mcp" in path
                else "OGC endpoints"
                if "/ogc" in path
                else "API documentation"
                if path in ["/api/docs", "/api/redoc", "/api/openapi.json"]
                else "Access checks"
                if "/turnstile/" in path
                else "Analytics capture"
                if path == "/api/v1/analytics/events"
                else "Resource API"
                if path.startswith("/api/v1/resources")
                else "Search API"
                if path.startswith("/api/v1/search")
                else "Other endpoints"
            )
            surfaces[surface] += n
            if row["metric_date"] == peak_day:
                category = (
                    "Turnstile status checks"
                    if path == "/api/v1/turnstile/status"
                    else "API documentation probes"
                    if path == "/api/docs"
                    else "Thumbnails"
                    if "thumbnail" in path
                    else "Resource endpoints"
                    if path.startswith("/api/v1/resources")
                    else "Analytics event capture"
                    if path == "/api/v1/analytics/events"
                    else "Robots and sitemaps"
                    if "sitemap" in path or "robots" in path
                    else "Everything else"
                )
                peak[category] += n
        metric = {
            "analytics_api_usage_logs": "requests",
            "analytics_searches": "searches",
            "analytics_events": "events",
        }.get(source)
        if metric:
            clients[
                (
                    (dim.get("client") or "Not declared").replace("Unknown", "Not declared"),
                    (dim.get("channel") or "Not declared").replace("Unknown", "Not declared"),
                )
            ][metric] += n

    def percentile(q):
        if not latency:
            return None
        target = (sum(latency.values()) - 1) * q
        lo = int(target)
        hi = lo + (target > lo)
        pos = 0
        vals = {}
        for value, n in sorted(latency.items()):
            for rank in [lo, hi]:
                if pos <= rank < pos + n:
                    vals[rank] = value
            pos += n
        return vals[lo] + (target - lo) * (vals[hi] - vals[lo])

    def resource(row):
        meta = content_metadata(doc["catalog"].get(row["id"], {}))
        attrs = meta.get("attributes", {})
        e = events[row["id"]]
        return dict(
            id=row["id"],
            title=row["title"],
            provider=", ".join(row.get("provider") or []),
            resourceClass=", ".join(attrs.get("resourceClasses") or []),
            resourceType=", ".join(attrs.get("resourceTypes") or []),
            views=row["views"],
            actions=e["events"] - row["views"],
            firstHalfEvents=e["first"],
            secondHalfEvents=e["second"],
        )

    def query_rows(report, key):
        return [
            dict(term=r["query"], count=r["count"])
            for r in report[key]
            if r["query"] not in ("", "Suppressed queries")
        ][:50]

    summary = dict(
        month=date.fromisoformat(doc["month"]).strftime("%B %Y"),
        exportedAt=date.fromisoformat(doc["catalogCapturedAt"][:10]).strftime("%B %-d, %Y"),
        requests=sep["totals"]["requests"],
        serverErrors=sep["totals"]["errors"],
        medianResponseMs=percentile(0.5),
        p95ResponseMs=percentile(0.95),
        searches=sep["totals"]["searches"],
        zeroResultSearches=sep["totals"]["zeroResults"],
        impressions=sep["totals"]["impressions"],
        events=sep["totals"]["events"],
        resourceViews=sep["totals"]["views"],
        downloadClicks=sep["totals"]["downloads"],
        resultClicks=sep["totals"]["resultOpens"],
        uniqueEngagedVisits=verified[period]["engaged_visits"],
    )
    september = dict(
        summary=summary,
        memberReport=member,
        provider=provider,
        dailyActivity=[
            dict(
                day=r["date"],
                requests=r["requests"],
                searches=r["searches"],
                events=r.get("events", 0),
            )
            for r in sep["daily"]
        ],
        topResources=[resource(r) for r in sep["resources"][:50]],
        topCollections=collection_searches([doc])[:50],
        topDownloads=[
            dict(
                id=r["id"],
                title=r["title"],
                provider=", ".join(r.get("provider") or []),
                resourceClass="",
                formatLabel="",
                clicks=r["downloads"],
                engagedVisits=None,
            )
            for r in sep["downloads"][:50]
        ],
        downloadResources=len(sep["downloads"]),
        discoveryViews=[
            dict(
                label=k.title(),
                count=sum(r["count"] for r in sep["discoveryViews"] if r["view"] == k),
                percent=sum(r["count"] for r in sep["discoveryViews"] if r["view"] == k)
                / max(summary["searches"], 1)
                * 100,
                color=COLORS[i],
            )
            for i, k in enumerate(["map", "gallery", "list"])
        ],
        resourceClassFilters=details["resourceClassFilters"],
        topSearches=dict(
            searches=summary["searches"],
            withQuery=details["withQuery"],
            distinctQueries=details["distinctQueries"],
            queries=query_rows(sep, "queries"),
            rankedSearches=sum(r["count"] for r in query_rows(sep, "queries")),
        ),
        searchSnapshot=dict(
            zeroQueries=query_rows(sep, "zeroQueries"),
            facets=[dict(field=r["facet"], count=r["count"]) for r in sep["facets"]],
        ),
        zeroBreakdown=dict(
            with_query=details["zeroWithQuery"],
            without_query=summary["zeroResultSearches"] - details["zeroWithQuery"],
        ),
        requestMix=[
            dict(
                label=k,
                count=mix[k],
                percent=mix[k] / max(summary["requests"], 1) * 100,
                color=COLORS[i],
            )
            for i, k in enumerate(
                ["API docs", "Access checks", "Analytics capture", "Everything else"]
            )
        ],
        peakApiTrafficBreakdown=[
            dict(
                label=k,
                detail=k,
                count=peak[k],
                percent=round(peak[k] / max(1, max(r["requests"] for r in sep["daily"])) * 100, 1),
            )
            for k in [
                "Turnstile status checks",
                "API documentation probes",
                "Resource endpoints",
                "Thumbnails",
                "Analytics event capture",
                "Robots and sitemaps",
                "Everything else",
            ]
        ],
        clients=dict(
            clients=[
                dict(
                    name=k[0],
                    channel=k[1],
                    requests=v["requests"],
                    searches=v["searches"],
                    events=v["events"],
                )
                for k, v in clients.items()
            ],
            surfaces=[
                dict(label=k, requests=surfaces[k])
                for k in [
                    "API documentation",
                    "Access checks",
                    "Other endpoints",
                    "Analytics capture",
                    "Resource API",
                    "Search API",
                    "OGC endpoints",
                    "MCP endpoints",
                ]
            ],
            recordedKeys=len(
                {
                    r["apiKey"]
                    for r in sep["clients"]
                    if r["apiKey"]
                    not in ["Not declared", "Not applicable", "None", "Unknown", "Anonymous"]
                }
            ),
            keyAttributedRequests=sum(
                r["requests"]
                for r in sep["clients"]
                if r["apiKey"]
                not in ["Not declared", "Not applicable", "None", "Unknown", "Anonymous"]
            ),
            unattributedKeyRequests=0,
            qgisUserAgentRequests=sep["totals"]["qgisUserAgentRequests"],
        ),
    )
    september["clients"]["unattributedKeyRequests"] = (
        summary["requests"] - september["clients"]["keyAttributedRequests"]
    )
    old = json.loads((output / "allTime2026.json").read_text())
    all_data = {
        k: v for k, v in old.items() if k not in ("providers", "codes", "downloads", "endpoints")
    }
    all_data.update(
        endExclusive=all_report["endExclusive"],
        publishedMonths=months,
        exportedAt=doc["catalogCapturedAt"],
        catalogDate=doc["catalogCapturedAt"][:10],
        searchTotals=dict(
            searches=all_report["totals"]["searches"],
            zeroResults=all_report["totals"]["zeroResults"],
            withQuery=all_details["withQuery"],
            distinctQueries=all_details["distinctQueries"],
        ),
        queries=query_rows(all_report, "queries"),
        zeroQueries=query_rows(all_report, "zeroQueries"),
        resourceClassFilters=all_details["resourceClassFilters"],
        facets=[dict(field=r["facet"], count=r["count"]) for r in all_report["facets"]],
        zeroWithQuery=all_details["zeroWithQuery"],
        resultClicks=all_report["totals"]["resultOpens"],
        searchViews=[dict(label=r["view"], count=r["count"]) for r in all_report["discoveryViews"]],
        resources=[
            dict(
                id=r["id"],
                title=r["title"],
                provider=", ".join(r.get("provider") or []),
                views=r["views"],
                downloads=r["downloads"],
                sources=r["sourceClicks"],
                impressions=r["impressions"],
            )
            for r in all_report["resources"][:50]
        ],
    )
    september_daily = [
        dict(
            day=r["date"],
            searches=r["searches"],
            zeroResults=r.get("zeroResults", 0),
            events=r.get("events", 0),
            views=r["views"],
            downloads=r["downloads"],
            requests=r["requests"],
            errors=r.get("errors", 0),
        )
        for r in sep["daily"]
    ]
    # The renderer's daily contract omits errors; recover them from preserved dimensions.
    errors = Counter()
    for r in doc["daily"]:
        if (
            r["dimensions"]["source"] == "analytics_api_usage_logs"
            and (r["dimensions"].get("status") or 0) >= 500
        ):
            errors[r["metric_date"]] += r["metrics"]["count"]
    for r in september_daily:
        r["errors"] = errors[r["day"]]
    # Start with the preserved July/August evidence; append every later month once.
    all_data["daily"] = old["daily"] + [
        dict(
            day=r["date"],
            **{
                k: r.get(k, 0)
                for k in (
                    "searches",
                    "zeroResults",
                    "events",
                    "views",
                    "downloads",
                    "requests",
                    "errors",
                )
            },
        )
        for r in all_report["daily"]
        if r["date"] >= "2026-09-01"
    ]
    extra = defaultdict(Counter)
    for source in docs[2:]:
        for r in source["daily"]:
            dim, metrics = r["dimensions"], r["metrics"]
            if dim["source"] == "analytics_events":
                extra[r["metric_date"]]["events"] += metrics["count"]
            if dim["source"] == "analytics_searches":
                extra[r["metric_date"]]["zeroResults"] += metrics.get("zeroResults", 0)
            if dim["source"] == "analytics_api_usage_logs" and (dim.get("status") or 0) >= 500:
                extra[r["metric_date"]]["errors"] += metrics["count"]
    for row in all_data["daily"]:
        row.update(extra[row["day"]])
    endpoints = json.loads((output / "reliabilityEndpoints2026.json").read_text())
    totals = defaultdict(Counter)
    for row in endpoints["periods"]["all"]:
        totals[row["label"]].update({k: row[k] for k in ("requests", "errors")})
    for month in months[2:]:
        endpoints["periods"][month] = endpoint_rows(reports[month]["endpoints"])
        for row in endpoints["periods"][month]:
            totals[row["label"]].update({k: row[k] for k in ("requests", "errors")})
    endpoints["periods"]["all"] = [
        dict(label=k, **v) for k, v in sorted(totals.items(), key=lambda x: -x[1]["requests"])
    ]
    historical_outcomes = json.loads((output / "outcomes2026.json").read_text())["periods"]
    for historical_period in ("2026-07", "2026-08"):
        for ranking in ("outlinks", "downloads"):
            for row in historical_outcomes[historical_period][ranking]:
                meta = content_metadata(
                    docs[["2026-07", "2026-08"].index(historical_period)]["catalog"].get(
                        row["id"], {}
                    )
                )
                row["title"] = meta.get("title") or row["id"]
                row["provider"] = ", ".join(content_providers(meta))
    payloads = {
        "popularHistory2026.json": {d["month"][:7]: popular_content(d) for d in docs[:-1]},
        f"month-{period}.json": september,
        "allTimeCurrent.json": all_data,
        "memberAllTimeCurrent.json": member_report(all_report),
        "outcomesCurrent.json": {
            "contentCatalogCapturedAt": doc.get(
                "contentCatalogCapturedAt", doc["catalogCapturedAt"]
            ),
            "catalogDate": doc["catalogCapturedAt"][:10],
            "exportedAt": doc["catalogCapturedAt"],
            "periods": {
                "2026-07": historical_outcomes["2026-07"],
                "2026-08": historical_outcomes["2026-08"],
                **{
                    m: outcomes(reports[m], search_details([docs[months.index(m)]]))
                    for m in months[2:]
                },
                "all": outcomes(all_report, all_details),
            },
        },
        "collectionSearchesCurrent.json": dict(
            collections=collection_searches(docs),
            method=(
                "Recomputed from complete preserved monthly search dimensions, "
                "including exclusions and legacy controls; collections can overlap."
            ),
        ),
        "reliabilityEndpointsCurrent.json": endpoints,
    }
    for name, data in payloads.items():
        (output / name).write_text(
            json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n"
        )
    print(f"Exported {period} and cumulative data for the established dashboard components.")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--period")
    p.add_argument("archives", nargs="+", type=Path)
    p.add_argument("--public", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--supplemental", type=Path, required=True)
    a = p.parse_args()
    run(a.archives, a.public, a.output, a.supplemental, a.period)
