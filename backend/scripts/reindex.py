#!/usr/bin/env python3
"""
Resilient, self-healing reindexer:
 - Streams DB rows in keyset pagination (no OFFSET gaps)
 - Indexes with per-document retries and structured failure logging
 - Runs a verify/repair loop to close any gaps (DB vs ES)
 - Exposes behavior via environment variables (see below)

Environment:
  - ELASTICSEARCH_INDEX: target index name (default: btaa_geospatial_api)
  - PUBLISHED_ONLY:      1/true to index only published rows (default: 1)
  - USE_B1G_PUBLICATION_STATE: 1/true to use b1g_publication_state_s (default: 0)
  - BATCH_SIZE:          DB fetch size (default: 2000)
  - MAX_RETRIES:         Per-document index retries (default: 3)
  - VERIFY_ROUNDS:       Max verify/repair iterations (default: 2)
  - FAILURE_LOG:         Path for structured failure log (default: logs/reindex_failures.log)
"""

import asyncio
import json
import logging
import os
import sys
from typing import AsyncIterator, Dict, Iterable, List, Optional, Set
from urllib.parse import unquote

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv

from app.elasticsearch.client import es
from app.elasticsearch.index import process_resource
from db.database import database

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def _env_bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return str(val).strip().lower() in {"1", "true", "t", "yes", "y"}


def _failure_logger() -> logging.Logger:
    path = os.getenv("FAILURE_LOG", "logs/reindex_failures.log")
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
    except Exception:
        return logger
    flog = logging.getLogger("reindex_failures")
    if not any(
        isinstance(h, logging.FileHandler) and getattr(h, "baseFilename", "") == path
        for h in flog.handlers
    ):
        fh = logging.FileHandler(path)
        fh.setLevel(logging.INFO)
        fh.setFormatter(logging.Formatter("%(message)s"))
        flog.addHandler(fh)
        flog.propagate = False
        flog.setLevel(logging.INFO)
    return flog


async def _db_id_stream(
    published_only: bool, use_b1g_pub_state: bool, batch_size: int
) -> AsyncIterator[List[str]]:
    """
    Yield lists of resource IDs using keyset pagination (ORDER BY id).
    """
    last_id: Optional[str] = None
    where_parts: List[str] = []
    params: Dict[str, object] = {}
    if published_only:
        if use_b1g_pub_state:
            where_parts.append("coalesce(b1g_publication_state_s, '') = 'published'")
        else:
            where_parts.append("publication_state = 'published'")

    while True:
        clause = " AND ".join(where_parts) if where_parts else "TRUE"
        if last_id is None:
            sql = f"SELECT id FROM resources WHERE {clause} ORDER BY id LIMIT :limit"
            params = {"limit": batch_size}
        else:
            sql = (
                f"SELECT id FROM resources WHERE {clause} "
                "AND id > :last_id ORDER BY id LIMIT :limit"
            )
            params = {"last_id": last_id, "limit": batch_size}

        rows = await database.fetch_all(sql, params)
        ids = [r["id"] for r in rows]
        if not ids:
            return
        yield ids
        last_id = ids[-1]


async def _db_rows_for_ids(ids: Iterable[str]) -> Dict[str, dict]:
    if not ids:
        return {}
    placeholders = ", ".join([f":id{i}" for i, _ in enumerate(ids)])
    params = {f"id{i}": rid for i, rid in enumerate(ids)}
    sql = f"SELECT * FROM resources WHERE id IN ({placeholders})"
    rows = await database.fetch_all(sql, params)
    return {str(r["id"]): dict(r) for r in rows}


async def _index_one(
    index_name: str, rid: str, document: dict, retries: int, flog: logging.Logger
) -> bool:
    attempt = 0
    while True:
        try:
            resp = await es.index(index=index_name, id=rid, document=document, refresh=False)
            ok = resp.get("result") in {"created", "updated"}
            if not ok:
                try:
                    flog.info(
                        json.dumps(
                            {
                                "id": rid,
                                "stage": "index",
                                "reason": "unexpected_result",
                                "response": resp,
                            }
                        )
                    )
                except Exception:
                    pass
            return ok
        except Exception as e:
            attempt += 1
            try:
                flog.info(
                    json.dumps(
                        {"id": rid, "stage": "index", "reason": "exception", "error": str(e)}
                    )
                )
            except Exception:
                pass
            if attempt > retries:
                return False
            await asyncio.sleep(min(2.0 * attempt, 8.0))


async def _verify_missing(
    index_name: str, published_only: bool, use_b1g_pub_state: bool
) -> Set[str]:
    # DB IDs
    if published_only:
        if use_b1g_pub_state:
            db_ids_sql = (
                "SELECT id FROM resources WHERE "
                "coalesce(b1g_publication_state_s, '') = 'published' "
                "ORDER BY id"
            )
        else:
            db_ids_sql = (
                "SELECT id FROM resources WHERE publication_state = 'published' ORDER BY id"
            )
    else:
        db_ids_sql = "SELECT id FROM resources ORDER BY id"
    db_rows = await database.fetch_all(db_ids_sql)
    db_ids = {row["id"] for row in db_rows}

    # ES IDs (scroll)
    es_ids: Set[str] = set()
    resp = await es.search(
        index=index_name,
        query={"match_all": {}},
        _source=False,
        size=1000,
        scroll="2m",
        sort=["_doc"],
    )
    rdict = resp.body if hasattr(resp, "body") else resp
    scroll_id = rdict.get("_scroll_id")
    hits = rdict.get("hits", {}).get("hits", [])
    for h in hits:
        es_ids.add(unquote(h["_id"]))
    while hits:
        resp = await es.scroll(scroll_id=scroll_id, scroll="2m")
        rdict = resp.body if hasattr(resp, "body") else resp
        scroll_id = rdict.get("_scroll_id")
        hits = rdict.get("hits", {}).get("hits", [])
        for h in hits:
            es_ids.add(unquote(h["_id"]))
    try:
        if scroll_id:
            await es.clear_scroll(scroll_id=scroll_id)
    except Exception:
        pass
    return set(db_ids) - es_ids


async def main():
    index_name = os.getenv("ELASTICSEARCH_INDEX", "btaa_geospatial_api")
    published_only = _env_bool("PUBLISHED_ONLY", True)
    use_b1g_pub_state = _env_bool("USE_B1G_PUBLICATION_STATE", False)
    batch_size = int(os.getenv("BATCH_SIZE", "2000"))
    max_retries = int(os.getenv("MAX_RETRIES", "3"))
    verify_rounds = int(os.getenv("VERIFY_ROUNDS", "2"))
    flog = _failure_logger()

    logger.info("=" * 70)
    logger.info(f"Starting resilient reindex into '{index_name}'")
    logger.info(
        f"published_only={published_only}, use_b1g_pub_state={use_b1g_pub_state}, "
        f"batch_size={batch_size}, max_retries={max_retries}, verify_rounds={verify_rounds}"
    )
    logger.info("=" * 70)

    total_attempted = 0
    total_indexed = 0
    total_errors = 0

    try:
        await database.connect()

        # Optionally drop index first, then ensure mappings exist
        drop_first = _env_bool("DROP_INDEX", False)
        try:
            exists = await es.indices.exists(index=index_name)
            if drop_first and exists:
                logger.info(f"DROP_INDEX=1 -> deleting existing index '{index_name}'")
                await es.indices.delete(index=index_name)
                exists = False
            if not exists:
                logger.info(f"Index '{index_name}' not found; initializing with mappings")
                from app.elasticsearch.client import init_elasticsearch

                await init_elasticsearch()
        except Exception as e:
            logger.error(f"Index initialization error: {e}", exc_info=True)
            raise

        # Phase 1: stream DB and index
        async for id_batch in _db_id_stream(published_only, use_b1g_pub_state, batch_size):
            rows = await _db_rows_for_ids(id_batch)
            for rid in id_batch:
                row = rows.get(rid)
                if not row:
                    continue
                total_attempted += 1
                try:
                    doc = await process_resource(row)
                except Exception as e:
                    total_errors += 1
                    try:
                        flog.info(
                            json.dumps(
                                {
                                    "id": rid,
                                    "stage": "process",
                                    "reason": "exception",
                                    "error": str(e),
                                }
                            )
                        )
                    except Exception:
                        pass
                    continue
                ok = await _index_one(index_name, rid, doc, max_retries, flog)
                if ok:
                    total_indexed += 1
                else:
                    total_errors += 1

            if total_attempted % max(1, batch_size) == 0:
                logger.info(
                    "Progress: attempted=%s, indexed=%s, errors=%s",
                    f"{total_attempted:,}",
                    f"{total_indexed:,}",
                    f"{total_errors:,}",
                )

        # One refresh to expose results
        try:
            await es.indices.refresh(index=index_name)
        except Exception:
            pass

        logger.info(
            f"Initial pass complete: attempted={total_attempted:,}, "
            f"indexed={total_indexed:,}, errors={total_errors:,}"
        )

        # Phase 2: verify/repair loop
        for round_i in range(1, verify_rounds + 1):
            missing = await _verify_missing(index_name, published_only, use_b1g_pub_state)
            if not missing:
                logger.info("✓ Verification passed: no missing resources")
                break
            logger.info(f"[verify round {round_i}] Found {len(missing):,} missing; repairing...")
            # Index missing synchronously with retries
            rows = await _db_rows_for_ids(missing)
            fixed = 0
            for rid in sorted(missing):
                row = rows.get(rid)
                if not row:
                    continue
                try:
                    doc = await process_resource(row)
                except Exception as e:
                    try:
                        flog.info(
                            json.dumps(
                                {
                                    "id": rid,
                                    "stage": "process",
                                    "reason": "exception",
                                    "error": str(e),
                                }
                            )
                        )
                    except Exception:
                        pass
                    continue
                ok = await _index_one(index_name, rid, doc, max_retries, flog)
                if ok:
                    fixed += 1
            try:
                await es.indices.refresh(index=index_name)
            except Exception:
                pass
            logger.info(f"[verify round {round_i}] Repair indexed {fixed:,} documents")
        else:
            logger.warning("Verification rounds exhausted; some resources may still be missing.")

        # Final report: compare counts
        # DB count
        if published_only:
            if use_b1g_pub_state:
                db_count_sql = (
                    "SELECT COUNT(*) FROM resources WHERE "
                    "coalesce(b1g_publication_state_s, '') = 'published'"
                )
            else:
                db_count_sql = (
                    "SELECT COUNT(*) FROM resources WHERE publication_state = 'published'"
                )
        else:
            db_count_sql = "SELECT COUNT(*) FROM resources"
        db_count = (await database.fetch_one(db_count_sql))[0]
        es_count = (await es.count(index=index_name)).get("count", 0)

        logger.info("=" * 70)
        logger.info("Resilient reindex complete")
        logger.info(
            json.dumps(
                {
                    "attempted": total_attempted,
                    "indexed": total_indexed,
                    "errors": total_errors,
                    "db_count": int(db_count),
                    "es_count": int(es_count),
                    "index": index_name,
                }
            )
        )
        logger.info("=" * 70)

    except Exception as e:
        logger.error(f"Resilient reindex failed: {e}", exc_info=True)
        sys.exit(1)
    finally:
        try:
            await database.disconnect()
        except Exception:
            pass
        try:
            await es.close()
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(main())
