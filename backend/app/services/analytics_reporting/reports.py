"""Generate public report contracts solely from preserved reporting documents."""

from collections import Counter, defaultdict
from datetime import date, timedelta

from .contract import (
    CALCULATION_VERSION,
    PRIVACY_VERSION,
    SCHEMA_VERSION,
    Visits,
    period_bounds,
    public_queries,
)
from .storage import canonical, checksum

REPORTS = ("overview", "comparison", "content", "discovery", "members", "clients", "platform")


def source_available(document, source):
    coverage = document["coverage"]
    return (
        coverage.get("complete") is True
        or coverage.get("sources", {}).get(source) is not None
        or coverage.get("aggregateSources", {}).get(source) is not None
    )


def ranked_queries(rows, zero=False):
    terms = {}
    for row in rows:
        count = row["zeroResults"] if zero else row["count"]
        if not count:
            continue
        term = terms.setdefault(
            row["query"],
            {
                "query": row["query"],
                "category": row["category"],
                "count": 0,
                "zeroResults": 0,
                "context": [],
                "resultTotals": {},
                "withheldContextCount": 0,
            },
        )
        term["count"] += count
        term["zeroResults"] += row["zeroResults"]
        distribution = row.get("zeroResultTotals" if zero else "resultTotals", {})
        for value, n in distribution.items():
            term["resultTotals"][value] = term["resultTotals"].get(value, 0) + n
        if count >= 3:
            term["context"].append(
                {"constraints": row["context"], "count": count, "resultTotals": distribution}
            )
        else:
            term["withheldContextCount"] += count
    published = public_queries(list(terms.values()))
    return sorted(
        published, key=lambda r: (r["query"] == "Suppressed queries", -r["count"], r["query"])
    )


def build_report(period, through, documents):
    start, end = period_bounds(period, through)
    selected = [d for d in documents if start <= date.fromisoformat(d["month"]) < end]
    totals = Counter(
        {
            k: 0
            for k in ("requests", "searches", "views", "downloads", "sourceClicks", "impressions")
        }
    )
    daily = defaultdict(Counter)
    queries, resources, clients, endpoints, facets = {}, {}, {}, {}, Counter()
    categories = Counter()
    latency = Counter()
    visits = Visits()
    members = {}
    member_resources, member_daily = {}, {}
    coverage = []
    collections = {}
    discovery_views = Counter()
    for document in selected:
        coverage.append(
            {
                "month": document["month"][:7],
                "sources": document["coverage"],
                "catalogCapturedAt": document.get("catalogCapturedAt"),
                "legacySource": (document.get("legacy") or {}).get("source"),
            }
        )
        catalog = document.get("catalog") or {}
        for sketch in document["visits"]:
            if sketch["audience"] == "discovery":
                visits.merge(Visits(sketch["registers"]))
        for row in document["daily"]:
            dim, metrics = row["dimensions"], row["metrics"]
            count = metrics["count"]
            day = str(row["metric_date"])
            source = dim["source"]
            client_key = (dim["client"], dim["channel"], dim.get("apiKey", "Not applicable"))
            client = clients.setdefault(
                client_key,
                {
                    "client": client_key[0],
                    "channel": client_key[1],
                    "apiKey": client_key[2],
                    "requests": 0,
                    "searches": 0,
                    "events": 0,
                },
            )
            if source == "analytics_searches":
                totals["searches"] += count
                totals["zeroResults"] += metrics.get("zeroResults", 0)
                totals["recordsWithoutToken"] += metrics.get("recordsWithoutToken", 0)
                daily[day]["searches"] += count
                client["searches"] += count
                key = canonical([dim["query"], dim["context"]])
                query = queries.setdefault(
                    key,
                    {
                        "query": dim["query"],
                        "context": dim["context"],
                        "category": dim["category"],
                        "resultTotals": {},
                        "zeroResultTotals": {},
                        "count": 0,
                        "zeroResults": 0,
                    },
                )
                query["count"] += count
                for metric, n in metrics.items():
                    for prefix, target in (
                        ("resultTotal:", "resultTotals"),
                        ("zeroResultTotal:", "zeroResultTotals"),
                    ):
                        if metric.startswith(prefix):
                            value = metric.split(":", 1)[1]
                            query[target][value] = query[target].get(value, 0) + n
                query["zeroResults"] += metrics.get("zeroResults", 0)
                categories[dim["category"]] += count
                discovery_views[dim.get("view") or "Unknown"] += count
                used_facets = {
                    name.split("[", 1)[1].split("]", 1)[0] if "[" in name else name
                    for name in dim["context"]
                    if "[" in name or name in ("geo", "year_range")
                }
                for facet in used_facets:
                    facets[facet] += count
            elif source == "analytics_api_usage_logs":
                totals["requests"] += count
                totals["qgisUserAgentRequests"] += metrics.get("qgisUserAgentRequests", 0)
                totals["errors"] += count if (dim.get("status") or 0) >= 500 else 0
                totals["durationSum"] += metrics.get("durationSum", 0)
                totals["durationCount"] += metrics.get("durationCount", 0)
                daily[day]["requests"] += count
                client["requests"] += count
                key = (dim["endpoint"], dim["method"], dim["status"])
                endpoint = endpoints.setdefault(
                    key, {"endpoint": key[0], "method": key[1], "status": key[2], "count": 0}
                )
                endpoint["count"] += count
                for k, n in metrics.items():
                    if k.startswith("latency:"):
                        latency[int(k.split(":")[1])] += n
            else:
                event = dim["event"]
                metric = {
                    "impression": "impressions",
                    "resource_view": "views",
                    "download_click": "downloads",
                    "visit_source_click": "sourceClicks",
                    "result_click": "resultOpens",
                }.get(event)
                if metric:
                    totals[metric] += count
                    daily[day][metric] += count
                if source == "analytics_events":
                    client["events"] += count
                    totals["events"] += count
                    totals["recordsWithoutToken"] += metrics.get("recordsWithoutToken", 0)
                identifier = dim.get("resource")
                if not identifier:
                    continue
                metadata = catalog.get(identifier, {})
                title = metadata.get("title") or identifier
                resource = resources.setdefault(
                    identifier,
                    {
                        "id": identifier,
                        "title": title,
                        "views": 0,
                        "downloads": 0,
                        "sourceClicks": 0,
                        "impressions": 0,
                    },
                )
                if metric:
                    resource[metric] = resource.get(metric, 0) + count
                    for collection_id in (metadata.get("attributes") or {}).get(
                        "collections"
                    ) or []:
                        collection = collections.setdefault(
                            collection_id,
                            {
                                "id": collection_id,
                                "title": (catalog.get(collection_id) or {}).get(
                                    "title", collection_id
                                ),
                                "views": 0,
                                "downloads": 0,
                                "impressions": 0,
                                "sourceClicks": 0,
                            },
                        )
                        collection[metric] = collection.get(metric, 0) + count
                provider = metadata.get("provider") or "Unmapped"
                code = metadata.get("code") or "Unmapped"
                for grouping, label in (("provider", provider), ("code", code)):
                    member = members.setdefault(
                        (grouping, label),
                        {
                            "grouping": grouping,
                            "name": label,
                            "views": 0,
                            "downloads": 0,
                            "impressions": 0,
                            "sourceClicks": 0,
                        },
                    )
                    if metric:
                        member[metric] = member.get(metric, 0) + count
                        detail = member_resources.setdefault(
                            (grouping, label, identifier),
                            {
                                "grouping": grouping,
                                "name": label,
                                "id": identifier,
                                "title": title,
                                "views": 0,
                                "downloads": 0,
                                "sourceClicks": 0,
                                "impressions": 0,
                            },
                        )
                        detail[metric] = detail.get(metric, 0) + count
                        trend = member_daily.setdefault(
                            (grouping, label, day),
                            {
                                "grouping": grouping,
                                "name": label,
                                "date": day,
                                "views": 0,
                                "downloads": 0,
                                "sourceClicks": 0,
                                "impressions": 0,
                            },
                        )
                        trend[metric] = trend.get(metric, 0) + count
    for document in selected:
        if not source_available(document, "analytics_api_usage_logs"):
            for row in (document.get("legacy") or {}).get("dailyApiRequests", []):
                daily[row["date"]]["requests"] = row["requests"]
    days = []
    day = start
    while day < end:
        known = any(
            d["month"][:7] == str(day)[:7] and d["coverage"].get("complete") for d in selected
        )
        zeros = (
            {
                k: 0
                for k in (
                    "requests",
                    "searches",
                    "views",
                    "downloads",
                    "sourceClicks",
                    "impressions",
                )
            }
            if known
            else {}
        )
        days.append({"date": str(day), **zeros, **dict(daily[str(day)])})
        day += timedelta(days=1)
    safe_queries = ranked_queries(list(queries.values()))
    zero_queries = ranked_queries(list(queries.values()), zero=True)
    inventory = Counter()
    if selected:
        for metadata in (selected[-1].get("catalog") or {}).values():
            inventory[("provider", metadata.get("provider") or "Unmapped")] += 1
            inventory[("code", metadata.get("code") or "Unmapped")] += 1
    for key, count in inventory.items():
        members.setdefault(
            key,
            {
                "grouping": key[0],
                "name": key[1],
                "views": 0,
                "downloads": 0,
                "impressions": 0,
                "sourceClicks": 0,
            },
        )["inventory"] = count
    for value in members.values():
        value.setdefault("inventory", 0)
        value["activeResources"] = sum(
            1
            for group, name, _ in member_resources
            if group == value["grouping"] and name == value["name"]
        )
    sample_count = sum(latency.values())
    p95, seen = None, 0
    for duration, count in sorted(latency.items()):
        seen += count
        if seen >= sample_count * 0.95:
            p95 = duration
            break
    source_months = {d["month"][:7] for d in selected}
    expected_months = {day["date"][:7] for day in days}
    complete = source_months == expected_months and all(
        d["coverage"].get("complete") is True for d in selected
    )
    comparison = []
    for document in documents if period[0].isdigit() else selected:
        counts = Counter()
        for row in document["daily"]:
            dim, values = row["dimensions"], row["metrics"]
            key = {
                "analytics_searches": "searches",
                "analytics_api_usage_logs": "requests",
                "analytics_search_impressions": "impressions",
            }.get(dim["source"])
            if key is None:
                key = {
                    "resource_view": "views",
                    "download_click": "downloads",
                    "visit_source_click": "sourceClicks",
                    "result_click": "resultOpens",
                }.get(dim.get("event"), "otherEvents")
            counts[key] += values["count"]
        for source, metric, field in (
            ("analytics_api_usage_logs", "requests", "requests"),
            ("analytics_search_impressions", "impressions", "impressions"),
        ):
            summary = (document.get("legacy") or {}).get("summary", {})
            if not source_available(document, source) and summary.get(field) is not None:
                counts[metric] = summary[field]
        comparison.append(
            {
                "month": document["month"][:7],
                "complete": document["coverage"].get("complete", False),
                **dict(counts),
            }
        )
    visits_complete = source_months == expected_months and all(
        d["coverage"].get("complete") is True
        or all(
            d["coverage"].get("sources", {}).get(source) is not None
            for source in ("analytics_searches", "analytics_events")
        )
        for d in selected
    )
    source_complete = {
        source: source_months == expected_months
        and all(source_available(d, source) for d in selected)
        for source in (
            "analytics_api_usage_logs",
            "analytics_searches",
            "analytics_events",
            "analytics_search_impressions",
        )
    }
    public_totals = dict(totals)
    for source, metrics in {
        "analytics_api_usage_logs": ("requests", "errors", "qgisUserAgentRequests"),
        "analytics_searches": ("searches", "zeroResults"),
        "analytics_events": ("events", "views", "downloads", "sourceClicks", "resultOpens"),
        "analytics_search_impressions": ("impressions",),
    }.items():
        if not source_complete[source]:
            for metric in metrics:
                public_totals[metric] = None
    # Saved additive monthly totals remain useful even when raw distributions
    # have expired. Never use them to invent endpoint counts or visit sketches.
    for source, metric, field in (
        ("analytics_api_usage_logs", "requests", "requests"),
        ("analytics_api_usage_logs", "errors", "serverErrors"),
        ("analytics_search_impressions", "impressions", "impressions"),
    ):
        if source_months != expected_months:
            continue
        values = []
        for document in selected:
            if source_available(document, source):
                values.append(
                    sum(
                        row["metrics"]["count"]
                        for row in document["daily"]
                        if row["dimensions"]["source"] == source
                        and (metric != "errors" or (row["dimensions"].get("status") or 0) >= 500)
                    )
                )
            else:
                values.append((document.get("legacy") or {}).get("summary", {}).get(field))
        if values and all(v is not None for v in values):
            public_totals[metric] = sum(values)
    legacy_p95 = None
    if len(selected) == 1 and period[0].isdigit():
        legacy_p95 = (selected[0].get("legacy") or {}).get("summary", {}).get("p95ResponseMs")
    result = {
        "sourceCoverage": source_complete,
        "schemaVersion": SCHEMA_VERSION,
        "calculationVersion": CALCULATION_VERSION,
        "privacyVersion": PRIVACY_VERSION,
        "period": period,
        "start": str(start),
        "endExclusive": str(end),
        "complete": complete,
        "coverage": coverage,
        "missingMonths": sorted(expected_months - source_months),
        "sources": {
            "overview": "Requests and discovery events; requests include automated traffic.",
            "comparison": "Calendar-month totals from the same sealed report revisions.",
            "content": "Recorded resource events and impressions, joined to each sealed catalog.",
            "discovery": "Rendered search result pages, including filter changes and pagination. "
            "Zero-result flags are preserved as recorded. Query disclosure requires three "
            "occurrences per context; automated suppression is not a privacy guarantee.",
            "members": "Provider uses schema_provider_s; contribution uses the saved code mapping. "
            "Inventory uses the last included catalog, not a sum across months.",
            "clients": "Declared clients and numeric API-key labels, not verified human identity.",
            "platform": "Saved statistics and logs; combined percentiles require distributions.",
        },
        "collections": sorted(collections.values(), key=lambda r: (-r["views"], r["id"])),
        "discoveryViews": [{"view": k, "count": n} for k, n in discovery_views.items()],
        "comparison": comparison,
        "memberResources": sorted(member_resources.values(), key=lambda r: (-r["views"], r["id"])),
        "memberDaily": sorted(member_daily.values(), key=lambda r: (r["date"], r["name"])),
        "totals": public_totals,
        "daily": days,
        "trackedVisits": {
            "value": visits.estimate() if visits_complete else None,
            "status": "estimated" if visits_complete else "unavailable",
            "relativeStandardError": 1.04 / (2**14) ** 0.5,
            "definition": "Distinct tab-scoped visit tokens; not unique people.",
        },
        "queries": safe_queries,
        "zeroQueries": zero_queries,
        "zeroCategories": [
            {"category": name, "count": count}
            for name, count in Counter(
                {
                    name: sum(q["zeroResults"] for q in queries.values() if q["category"] == name)
                    for name in categories
                }
            ).items()
            if count
        ],
        "zeroResultPercent": 100 * totals["zeroResults"] / totals["searches"]
        if totals["searches"] and source_complete["analytics_searches"]
        else None,
        "categories": [{"category": k, "count": v} for k, v in categories.most_common()],
        "facets": [{"facet": k, "count": v} for k, v in facets.most_common()],
        "resources": sorted(resources.values(), key=lambda r: (-r["views"], r["id"])),
        "members": sorted(members.values(), key=lambda r: (r["grouping"], r["name"])),
        "clients": sorted(clients.values(), key=lambda r: (-r["requests"], r["client"])),
        "endpoints": sorted(endpoints.values(), key=lambda r: (-r["count"], r["endpoint"])),
        "latency": {
            "meanMs": totals["durationSum"] / totals["durationCount"]
            if totals["durationCount"] and source_complete["analytics_api_usage_logs"]
            else None,
            "p95Ms": p95 if source_complete["analytics_api_usage_logs"] else legacy_p95,
        },
        "unavailable": {
            "uniqueVisitors": "No persistent person identifier is collected.",
            "pageviews": "General page-view coverage has not been verified.",
        },
    }
    result["revision"] = checksum(result)
    return result
