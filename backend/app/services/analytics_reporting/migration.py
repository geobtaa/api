"""Read-only historical migration into the same portable archive contract."""

from collections import Counter
from datetime import date, datetime, timezone

from sqlalchemy import text

from .archive import validate_document
from .contract import SOURCES, Visits, next_month
from .pipeline import read_catalog
from .storage import FIELDS, checksum, contribution, dimensions


def export_readonly(conn, month: date, expected: dict, legacy=None):
    """Caller uses a repeatable-read READ ONLY transaction; no DDL or writes."""
    fields = ",".join("'" + key + "'" for key in FIELDS)
    grouped, sketches, receipts = {}, {}, []
    observed = {}
    for source, timestamp in SOURCES.items():
        query = text(f"""SELECT r.id,b.body,md5(b.body::text) AS fingerprint
            FROM {source} r CROSS JOIN LATERAL (
              SELECT coalesce(jsonb_object_agg(key,CASE WHEN key='properties'
                THEN jsonb_build_object('constraints',value->'constraints') ELSE value END),
                '{{}}'::jsonb) || jsonb_build_object('qgisAgent',
                  position('qgis' in lower(coalesce(to_jsonb(r)->>'user_agent','')))>0) AS body
                FROM jsonb_each(to_jsonb(r)) WHERE key IN ({fields})
            ) b WHERE partition_month=:month ORDER BY r.id""")
        observed[source] = 0
        result = conn.execution_options(stream_results=True).execute(query, {"month": month})
        for record in result.mappings():
            row = record["body"]
            day = date.fromisoformat(row[timestamp][:10])
            dim = dimensions(source, row)
            key = (day, checksum(dim))
            grouped.setdefault(
                key,
                {
                    "metric_date": day,
                    "dimension_key": key[1],
                    "dimensions": dim,
                    "metrics": Counter(),
                },
            )
            delta = contribution(source, row)
            grouped[key]["metrics"].update(delta)
            receipts.append(
                {
                    "source": source,
                    "source_id": record["id"],
                    "fingerprint": record["fingerprint"],
                    "metric_date": day,
                    "dimension_key": key[1],
                    "contribution": dict(delta),
                }
            )
            if source != "analytics_search_impressions":
                audience = "api" if source == "analytics_api_usage_logs" else "discovery"
                if (day, audience) not in sketches:
                    sketches[(day, audience)] = Visits()
                sketches[(day, audience)].add(row.get("visit_token"))
            observed[source] += 1
        result.close()
        conn.execution_options(stream_results=False)
        if expected.get(source) is not None and observed[source] != expected[source]:
            raise ValueError(f"Historical baseline changed for {month} {source}")
    aggregate_sources = {}
    if observed["analytics_search_impressions"] == 0 and legacy is not None:
        exists = conn.execute(
            text("SELECT to_regclass('analytics_daily_resource_impressions') AS name")
        )
        has_rollup = list(exists.mappings())[0]["name"] is not None
        if has_rollup:
            rows = conn.execute(
                text("""SELECT metric_date,resource_id,impression_count
                FROM analytics_daily_resource_impressions
                WHERE metric_date>=:month AND metric_date<:end
                ORDER BY metric_date,resource_id"""),
                {"month": month, "end": next_month(month)},
            )
            total = 0
            for index, row in enumerate(rows.mappings(), start=1):
                day = date.fromisoformat(str(row["metric_date"]))
                dim = dimensions(
                    "analytics_search_impressions", {"resource_id": row["resource_id"]}
                )
                key = (day, checksum(dim))
                count = int(row["impression_count"])
                grouped[key] = {
                    "metric_date": day,
                    "dimension_key": key[1],
                    "dimensions": dim,
                    "metrics": {"count": count},
                }
                receipts.append(
                    {
                        "source": "analytics_search_impressions",
                        "source_id": -index,
                        "fingerprint": checksum(dict(row)),
                        "metric_date": day,
                        "dimension_key": key[1],
                        "contribution": {"count": count},
                    }
                )
                total += count
            if total == legacy.get("summary", {}).get("impressions"):
                aggregate_sources["analytics_search_impressions"] = total
    document = {
        "schemaVersion": 1,
        "legacy": legacy,
        "month": str(month),
        "generation": len(receipts) + 1,
        "coverage": {
            "complete": all(expected.get(s) is not None for s in SOURCES),
            "sources": expected,
            "aggregateSources": aggregate_sources,
            "observed": observed,
            "basis": "read-only source export reconciled to independent saved baselines",
        },
        "catalog": read_catalog(conn),
        "catalogCapturedAt": datetime.now(timezone.utc),
        "daily": [grouped[k] for k in sorted(grouped)],
        "visits": [
            {
                "metric_date": day,
                "audience": audience,
                "registers": sketches[(day, audience)].registers,
            }
            for day, audience in sorted(sketches)
        ],
        "receipts": sorted(receipts, key=lambda r: (r["source"], r["source_id"])),
        "deliveries": [],
    }
    validate_document(document)
    return document
