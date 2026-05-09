#!/usr/bin/env python3
"""Report thumbnail capture completeness by source bucket."""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.config import DATABASE_URL  # noqa: E402
from db.sync_engine import create_app_sync_engine  # noqa: E402

SOURCE_ORDER = {
    "iiif": 1,
    "b1g_image": 2,
    "schema_thumbnail": 3,
    "service": 4,
    "cog": 5,
    "pmtiles": 6,
    "schema_image": 7,
    "bridge_asset": 8,
    "no_source": 9,
}

OUTCOME_COLUMNS = (
    "success",
    "placeheld",
    "failed",
    "queued",
    "stale_success",
    "not_attempted",
    "no_source",
    "restricted",
)


def _sync_database_url() -> str:
    return DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")


def _scope_condition(scope: str) -> str:
    if scope == "urban":
        return "'b1g_urbanBaseLayers' = ANY(COALESCE(r.\"pcdm_memberOf_sm\", ARRAY[]::varchar[]))"
    if scope == "iiif":
        return "(COALESCE(r.dct_references_s, '') ILIKE '%iiif%' OR COALESCE(d.has_iiif, false))"
    return "TRUE"


def _classified_cte(scope: str) -> str:
    return f"""
WITH dist AS (
    SELECT
        rd.resource_id,
        BOOL_OR(
            COALESCE(dt.distribution_uri, '') ILIKE '%iiif%'
            OR COALESCE(rd.url, '') ILIKE '%iiif%'
        ) AS has_iiif,
        BOOL_OR(
            COALESCE(dt.distribution_uri, '') = 'https://github.com/protomaps/PMTiles'
            OR COALESCE(rd.url, '') ILIKE '%.pmtiles%'
            OR COALESCE(rd.url, '') ILIKE '%.pmtiles?%'
        ) AS has_pmtiles,
        BOOL_OR(
            COALESCE(dt.distribution_uri, '') = 'https://github.com/cogeotiff/cog-spec'
            OR COALESCE(rd.url, '') ~* '\\.tiff?(\\?|$)'
            OR COALESCE(rd.url, '') ILIKE '%geotiff%'
            OR COALESCE(rd.url, '') ILIKE '%display_raster%'
        ) AS has_cog,
        BOOL_OR(
            COALESCE(dt.distribution_uri, '') ILIKE '%serviceType%'
            OR COALESCE(dt.distribution_uri, '') ILIKE '%/ogc/wms%'
            OR COALESCE(dt.distribution_uri, '') ILIKE '%/ogc/tms%'
            OR COALESCE(rd.url, '') ILIKE '%/arcgis/rest/services/%'
        ) AS has_service
    FROM resource_distributions rd
    LEFT JOIN distribution_types dt ON dt.id = rd.distribution_type_id
    GROUP BY rd.resource_id
),
asset AS (
    SELECT
        resource_id,
        TRUE AS has_bridge_asset
    FROM resource_assets
    WHERE thumbnail IS TRUE
      AND NULLIF(BTRIM(file_url), '') IS NOT NULL
    GROUP BY resource_id
),
base AS (
    SELECT
        r.id,
        r.dct_title_s,
        COALESCE(r.dct_references_s, '') AS refs,
        COALESCE(r.b1g_image_ss, '') AS b1g_image,
        COALESCE(r."dct_accessRights_s", '') AS access_rights,
        COALESCE(d.has_iiif, false) AS has_iiif,
        COALESCE(d.has_pmtiles, false) AS has_pmtiles,
        COALESCE(d.has_cog, false) AS has_cog,
        COALESCE(d.has_service, false) AS has_service,
        COALESCE(asset.has_bridge_asset, false) AS has_bridge_asset,
        s.state,
        s.source_type,
        s.source_url,
        s.source_hash,
        (
            gva.asset_hash IS NOT NULL
            AND gva.byte_size > 0
            AND gva.content_type LIKE 'image/%'
        ) AS has_durable_thumbnail
    FROM resources r
    LEFT JOIN dist d ON d.resource_id = r.id
    LEFT JOIN asset ON asset.resource_id = r.id
    LEFT JOIN resource_thumbnail_state s ON s.resource_id = r.id
    LEFT JOIN generated_visual_assets gva
        ON gva.asset_hash = s.source_hash
       AND gva.asset_kind = 'thumbnail'
    WHERE {_scope_condition(scope)}
),
sourced AS (
    SELECT
        *,
        CASE
            WHEN has_iiif OR refs ILIKE '%iiif%' THEN 'iiif'
            WHEN NULLIF(BTRIM(b1g_image), '') IS NOT NULL THEN 'b1g_image'
            WHEN refs ILIKE '%schema.org/thumbnailUrl%' THEN 'schema_thumbnail'
            WHEN has_service
              OR refs ILIKE '%serviceType%'
              OR refs ILIKE '%/ogc/wms%'
              OR refs ILIKE '%/ogc/tms%'
              OR refs ILIKE '%/arcgis/rest/services/%' THEN 'service'
            WHEN has_cog
              OR refs ILIKE '%cogeotiff%'
              OR refs ~* '\\.tiff?(\\?|")' THEN 'cog'
            WHEN has_pmtiles
              OR refs ILIKE '%PMTiles%'
              OR refs ILIKE '%.pmtiles%' THEN 'pmtiles'
            WHEN refs ILIKE '%schema.org/image%' THEN 'schema_image'
            WHEN has_bridge_asset THEN 'bridge_asset'
            ELSE 'no_source'
        END AS source_bucket
    FROM base
),
classified AS (
    SELECT
        *,
        CASE
            WHEN LOWER(access_rights) = 'restricted' THEN 'restricted'
            WHEN state = 'success' AND has_durable_thumbnail THEN 'success'
            WHEN state = 'success' THEN 'stale_success'
            WHEN state = 'placeheld' THEN 'placeheld'
            WHEN state = 'failure' THEN 'failed'
            WHEN state = 'queued' THEN 'queued'
            WHEN source_bucket = 'no_source' THEN 'no_source'
            ELSE 'not_attempted'
        END AS outcome
    FROM sourced
)
"""


def _summary_sql(scope: str) -> str:
    outcome_counts = ",\n        ".join(
        f"COUNT(*) FILTER (WHERE outcome = '{column}')::bigint AS {column}"
        for column in OUTCOME_COLUMNS
    )
    return (
        _classified_cte(scope)
        + f"""
SELECT
    source_bucket,
    COUNT(*)::bigint AS total,
    {outcome_counts}
FROM classified
GROUP BY source_bucket
ORDER BY
    CASE source_bucket
        WHEN 'iiif' THEN 1
        WHEN 'b1g_image' THEN 2
        WHEN 'schema_thumbnail' THEN 3
        WHEN 'service' THEN 4
        WHEN 'cog' THEN 5
        WHEN 'pmtiles' THEN 6
        WHEN 'schema_image' THEN 7
        WHEN 'bridge_asset' THEN 8
        ELSE 9
    END,
    source_bucket;
"""
    )


def _missing_sql(scope: str) -> str:
    return (
        _classified_cte(scope)
        + """
SELECT
    id,
    dct_title_s,
    source_bucket,
    outcome,
    state,
    source_type,
    source_hash
FROM classified
WHERE outcome <> 'success'
ORDER BY
    CASE source_bucket
        WHEN 'iiif' THEN 1
        WHEN 'b1g_image' THEN 2
        WHEN 'schema_thumbnail' THEN 3
        WHEN 'service' THEN 4
        WHEN 'cog' THEN 5
        WHEN 'pmtiles' THEN 6
        WHEN 'schema_image' THEN 7
        WHEN 'bridge_asset' THEN 8
        ELSE 9
    END,
    id
LIMIT :limit;
"""
    )


def _rows_to_dicts(rows: list[Any]) -> list[dict[str, Any]]:
    return [dict(row._mapping) for row in rows]


def _total_row(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = {"source_bucket": "TOTAL", "total": 0}
    for column in OUTCOME_COLUMNS:
        total[column] = 0
    for row in rows:
        total["total"] += int(row["total"] or 0)
        for column in OUTCOME_COLUMNS:
            total[column] += int(row[column] or 0)
    return total


def _success_pct(row: dict[str, Any]) -> float:
    total = int(row["total"] or 0)
    if total <= 0:
        return 100.0
    return round((int(row["success"] or 0) / total) * 100, 2)


def _format_table(rows: list[dict[str, Any]], sample_rows: list[dict[str, Any]]) -> str:
    output: list[str] = []
    headings = [
        "source",
        "total",
        "ok",
        "ok%",
        "held",
        "fail",
        "queue",
        "stale",
        "todo",
        "none",
        "restr",
    ]
    table_rows = [*rows, _total_row(rows)]
    widths = {heading: len(heading) for heading in headings}
    rendered_rows = []
    for row in table_rows:
        rendered = {
            "source": str(row["source_bucket"]),
            "total": str(row["total"]),
            "ok": str(row["success"]),
            "ok%": f"{_success_pct(row):.2f}",
            "held": str(row["placeheld"]),
            "fail": str(row["failed"]),
            "queue": str(row["queued"]),
            "stale": str(row["stale_success"]),
            "todo": str(row["not_attempted"]),
            "none": str(row["no_source"]),
            "restr": str(row["restricted"]),
        }
        rendered_rows.append(rendered)
        for heading in headings:
            widths[heading] = max(widths[heading], len(rendered[heading]))

    output.append("  ".join(heading.ljust(widths[heading]) for heading in headings))
    output.append("  ".join("-" * widths[heading] for heading in headings))
    for rendered in rendered_rows:
        output.append("  ".join(rendered[heading].ljust(widths[heading]) for heading in headings))

    if sample_rows:
        output.append("")
        output.append("missing sample:")
        for row in sample_rows:
            title = str(row.get("dct_title_s") or "").replace("\n", " ")[:90]
            output.append(f"- {row['id']} | {row['source_bucket']} | {row['outcome']} | {title}")
    return "\n".join(output)


def _write_csv(rows: list[dict[str, Any]]) -> None:
    fieldnames = ["source_bucket", "total", *OUTCOME_COLUMNS, "success_pct"]
    writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames)
    writer.writeheader()
    for row in [*rows, _total_row(rows)]:
        out = dict(row)
        out["success_pct"] = _success_pct(row)
        writer.writerow(out)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Report thumbnail completeness.")
    parser.add_argument(
        "--scope",
        choices=("all", "urban", "iiif"),
        default=os.getenv("THUMBNAIL_REPORT_SCOPE", "all"),
    )
    parser.add_argument(
        "--format",
        choices=("table", "json", "csv"),
        default=os.getenv("THUMBNAIL_REPORT_FORMAT", "table"),
    )
    parser.add_argument(
        "--show-missing",
        type=int,
        default=int(os.getenv("THUMBNAIL_REPORT_SHOW_MISSING", "0") or 0),
    )
    parser.add_argument(
        "--fail-under",
        type=float,
        default=(
            float(os.getenv("THUMBNAIL_REPORT_FAIL_UNDER"))
            if os.getenv("THUMBNAIL_REPORT_FAIL_UNDER")
            else None
        ),
        help="Exit nonzero if overall success percentage is below this value.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    engine = create_app_sync_engine(_sync_database_url())
    with engine.begin() as conn:
        rows = _rows_to_dicts(conn.execute(text(_summary_sql(args.scope))).fetchall())
        sample_rows: list[dict[str, Any]] = []
        if args.show_missing > 0:
            sample_rows = _rows_to_dicts(
                conn.execute(
                    text(_missing_sql(args.scope)), {"limit": args.show_missing}
                ).fetchall()
            )

    total = _total_row(rows)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": args.scope,
        "summary": {**total, "success_pct": _success_pct(total)},
        "by_source": [{**row, "success_pct": _success_pct(row)} for row in rows],
        "missing_sample": sample_rows,
    }

    if args.format == "json":
        print(json.dumps(payload, indent=2, default=str))
    elif args.format == "csv":
        _write_csv(rows)
    else:
        print(f"thumbnail completeness | scope={args.scope}")
        print(_format_table(rows, sample_rows))

    if args.fail_under is not None and payload["summary"]["success_pct"] < args.fail_under:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
