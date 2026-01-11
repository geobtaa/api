"""
Debug tool: find resources that exist in Postgres but are missing from Elasticsearch,
then attempt to index them individually and record the exact failure reasons.

Typical usage (inside the backend container / venv):

    python backend/scripts/debug_index_missing_resources.py --repo edu.stanford.purl --limit 50

You can also run it for all resources (may take a while):

    python backend/scripts/debug_index_missing_resources.py --limit 50
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select

# Allow running this script from the repo root (so `import app...` works).
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.elasticsearch.client import es
from app.elasticsearch.index import process_resource
from db.database import database
from db.models import resources


def _parse_args(argv: List[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--repo",
        dest="repo_name",
        default=None,
        help="Limit to resources tagged with b1g_adminTags_sm containing ogm_repo:<repo> (e.g. edu.stanford.purl)",
    )
    p.add_argument(
        "--index",
        dest="index_name",
        default=None,
        help="Elasticsearch index name (default: ELASTICSEARCH_INDEX env var in app config).",
    )
    p.add_argument(
        "--limit",
        dest="limit",
        type=int,
        default=100,
        help="Max number of missing IDs to attempt indexing for.",
    )
    p.add_argument(
        "--scan-max",
        dest="scan_max",
        type=int,
        default=0,
        help="Max number of DB IDs to scan when looking for missing docs (0 = no cap).",
    )
    p.add_argument(
        "--batch",
        dest="batch_size",
        type=int,
        default=500,
        help="Batch size for Elasticsearch _mget existence checks.",
    )
    p.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        help="Only detect missing IDs; do not attempt indexing.",
    )
    return p.parse_args(argv)


async def _iter_db_ids(repo_name: Optional[str], scan_max: int) -> List[str]:
    """Return a (possibly capped) list of candidate resource IDs to check."""
    ids: List[str] = []
    last_id: Optional[str] = None

    while True:
        q = select(resources.c.id).order_by(resources.c.id).limit(5000)
        if last_id is not None:
            q = q.where(resources.c.id > last_id)
        if repo_name:
            tag = f"ogm_repo:{repo_name}"
            # b1g_adminTags_sm is ARRAY(String)
            q = q.where(resources.c.b1g_adminTags_sm.any(tag))

        rows = await database.fetch_all(q)
        if not rows:
            break

        for r in rows:
            rid = (dict(r)).get("id")
            if rid:
                ids.append(str(rid))
                if scan_max and len(ids) >= scan_max:
                    return ids

        last_id = (dict(rows[-1])).get("id")
        if not last_id:
            break

    return ids


async def _mget_missing_ids(index_name: str, ids: List[str], batch_size: int) -> List[str]:
    missing: List[str] = []

    for i in range(0, len(ids), batch_size):
        batch = ids[i : i + batch_size]
        resp = await es.mget(index=index_name, ids=batch)
        docs = resp.get("docs", [])
        for d in docs:
            if not d.get("found"):
                mid = d.get("_id")
                if mid:
                    missing.append(str(mid))

    return missing


async def _index_one(index_name: str, resource_id: str) -> Tuple[bool, Optional[str]]:
    """Attempt to index a single resource by id; return (ok, error_string)."""
    row = await database.fetch_one(select(resources).where(resources.c.id == resource_id))
    if not row:
        return False, "missing_in_db"

    processed = await process_resource(dict(row))
    if not processed or not processed.get("id"):
        return False, "process_resource_returned_empty"

    try:
        await es.index(index=index_name, id=processed["id"], document=processed, refresh="wait_for")
        return True, None
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


async def main(argv: List[str]) -> int:
    args = _parse_args(argv)
    index_name = args.index_name or "btaa_geospatial_api"

    await database.connect()
    try:
        # Gather candidate IDs from DB
        ids = await _iter_db_ids(args.repo_name, args.scan_max)
        print(f"db_candidates={len(ids)} repo={args.repo_name or '*'} index={index_name}")
        if not ids:
            return 0

        # Find which are missing in ES
        missing_ids = await _mget_missing_ids(index_name, ids, args.batch_size)
        print(f"missing_in_es={len(missing_ids)}")

        if args.dry_run or args.limit <= 0 or not missing_ids:
            return 0

        # Attempt to index missing docs individually
        error_types = Counter()
        attempted = 0
        fixed = 0

        for rid in missing_ids[: args.limit]:
            attempted += 1
            ok, err = await _index_one(index_name, rid)
            if ok:
                fixed += 1
                continue
            err_str = err or "unknown_error"
            error_types[err_str.split(":", 1)[0]] += 1
            print(json.dumps({"id": rid, "ok": False, "error": err_str}))

        print(
            json.dumps(
                {
                    "attempted": attempted,
                    "fixed": fixed,
                    "still_missing": max(0, attempted - fixed),
                    "error_types": dict(error_types),
                },
                indent=2,
            )
        )
        return 0
    finally:
        await database.disconnect()
        try:
            await es.close()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main(sys.argv[1:])))

