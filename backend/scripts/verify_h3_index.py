#!/usr/bin/env python3
"""Verify H3 pyramid fields (h3_res2..h3_res8, geo_or_near_global) in Elasticsearch.

Run from repo root with backend venv active:

    python backend/scripts/verify_h3_index.py

Uses ELASTICSEARCH_URL and ELASTICSEARCH_INDEX from env.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv

load_dotenv()

from app.elasticsearch.client import es  # noqa: E402 (load_dotenv must run first)


async def main() -> None:
    index = os.getenv("ELASTICSEARCH_INDEX", "btaa_geospatial_api")

    # 1. Sample docs: fetch a few with H3 + geo fields
    sample = await es.search(
        index=index,
        size=5,
        track_total_hits=True,
        _source=[
            "id",
            "h3_res2",
            "h3_res3",
            "h3_res4",
            "h3_res5",
            "h3_res6",
            "h3_res7",
            "h3_res8",
            "geo_or_near_global",
            "bbox_diagonal_km",
            "geo_global",
            "dcat_centroid",
        ],
        query={"match_all": {}},
        sort=[{"id.keyword": {"order": "asc", "missing": "_last"}}],
    )
    hits = (sample.get("hits") or {}).get("hits") or []
    total = (sample.get("hits") or {}).get("total") or {}
    total_count = total.get("value", total) if isinstance(total, dict) else total

    print(f"Index: {index}")
    print(f"Total documents: {total_count}")
    print()

    # 2. Count docs that have h3_res5 (eligible for hex map)
    with_h3 = await es.count(
        index=index,
        query={"exists": {"field": "h3_res5"}},
    )
    n_with_h3 = with_h3.get("count") or 0
    print(f"Documents with h3_res5: {n_with_h3}")

    # 3. Global bucket count (geo_or_near_global)
    global_agg = await es.search(
        index=index,
        size=0,
        query={"match_all": {}},
        aggs={
            "global_bucket": {
                "filter": {
                    "bool": {
                        "should": [
                            {"term": {"geo_global": True}},
                            {"range": {"bbox_diagonal_km": {"gt": 15_000}}},
                        ]
                    }
                }
            }
        },
    )
    gb = (global_agg.get("aggregations") or {}).get("global_bucket") or {}
    n_global = int(gb.get("doc_count", 0))
    print(f"Documents geo_or_near_global (global bucket): {n_global}")

    # 4. Terms agg on h3_res5 (sanity check)
    terms_agg = await es.search(
        index=index,
        size=0,
        query={"exists": {"field": "h3_res5"}},
        aggs={"by_h3": {"terms": {"field": "h3_res5", "size": 10, "min_doc_count": 1}}},
    )
    by_h3 = (terms_agg.get("aggregations") or {}).get("by_h3") or {}
    buckets = by_h3.get("buckets") or []
    print(f"H3 res5 distinct cells (top 10): {len(buckets)}")
    for b in buckets[:5]:
        print(f"  {b.get('key')}: {b.get('doc_count')}")

    print()
    print("Sample documents (first 3):")
    for i, h in enumerate(hits[:3]):
        src = h.get("_source") or {}
        pid = src.get("id", "?")
        has_h3 = "h3_res5" in src
        geo = src.get("geo_or_near_global")
        diag = src.get("bbox_diagonal_km")
        print(
            f"  [{i + 1}] id={pid} h3_res5={'yes' if has_h3 else 'no'} "
            f"geo_or_near_global={geo} bbox_diagonal_km={diag}"
        )
        if has_h3:
            print(f"       h3_res5={src.get('h3_res5')}")

    await es.close()
    print()
    print("H3 pyramid verification complete.")


if __name__ == "__main__":
    asyncio.run(main())
