from __future__ import annotations

import json
import logging
import time
from datetime import date, datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.services.distribution_sync import (
    sync_distributions_for_batch,
    sync_distributions_for_resource,
)
from app.services.ogm_harvest.aardvark_reader import extract_record_id
from app.services.ogm_harvest.repository import OGMHarvestRepository
from app.services.relationship_sync import (
    sync_relationships_for_batch,
    sync_relationships_for_resource_ids,
)
from db.database import database
from db.models import resources

logger = logging.getLogger(__name__)


def derive_repo_alias(repo_name: str) -> Optional[str]:
    parts = [p for p in (repo_name or "").split(".") if p]
    if len(parts) >= 2 and parts[0] == "edu":
        return parts[1]
    if parts:
        return parts[0]
    return None


def _parse_iso_datetime(value: str) -> Optional[datetime]:
    """
    Parse common ISO8601 timestamp strings into datetime.
    Handles trailing 'Z' (UTC) and offsets.
    """
    s = (value or "").strip()
    if not s:
        return None
    try:
        # datetime.fromisoformat doesn't accept "Z"
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        # DB columns are TIMESTAMP (no tz). Normalize tz-aware timestamps to naive UTC.
        if isinstance(dt, datetime) and dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except Exception:
        # Try a common fallback
        try:
            if value.endswith("Z"):
                dt = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
                return dt  # already naive UTC
        except Exception:
            return None
    return None


def _parse_iso_date(value: str) -> Optional[date]:
    """
    Parse common ISO8601 date strings into date.
    Accepts full timestamp strings by taking the date portion.
    """
    s = (value or "").strip()
    if not s:
        return None
    try:
        # If it looks like a timestamp, use only date portion.
        if "T" in s:
            s = s.split("T", 1)[0]
        return date.fromisoformat(s)
    except Exception:
        return None


def _normalize_scalar_string(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, list):
        values = [str(v).strip() for v in value if str(v).strip()]
        return values[0] if values else None
    normalized = str(value).strip()
    return normalized or None


class OGMResourceImporter:
    """
    Import Aardvark records into the `resources` table (UPSERT).

    - Injects repo tags into b1g_adminTags_sm (ogm_repo:<repo>, ogm:<alias>)
    - Normalizes common field types (arrays, ints, bools, JSON blobs)
    """

    def __init__(self, repo: Optional[OGMHarvestRepository] = None):
        self.repo = repo or OGMHarvestRepository()
        self._resource_columns_cache: Optional[Set[str]] = None

    async def _resource_columns_in_db(self) -> Set[str]:
        """Return current resources table columns from the connected DB."""
        if self._resource_columns_cache is not None:
            return self._resource_columns_cache

        rows = await database.fetch_all(
            text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'resources'
                """
            )
        )
        cols = set()
        for r in rows:
            try:
                name = r["column_name"]
            except Exception:
                name = None
            if name:
                cols.add(str(name))
        if not cols:
            cols = {c.name for c in resources.c}
        self._resource_columns_cache = cols
        return cols

    def _normalize_record(self, record: Dict[str, Any], repo_name: str) -> Dict[str, Any]:
        out: Dict[str, Any] = {}

        # Ensure id exists
        rid = extract_record_id(record)
        if rid:
            out["id"] = str(rid)

        # Copy known fields verbatim first
        for col in resources.c:
            name = col.name
            if name == "id":
                continue
            if name in record:
                out[name] = record.get(name)

        # Normalize gbl_indexYear_im to list[int] (db column is ARRAY(Integer))
        if "gbl_indexYear_im" in out:
            v = out.get("gbl_indexYear_im")
            if isinstance(v, list):
                out["gbl_indexYear_im"] = [int(x) for x in v if str(x).isdigit()] or None
            elif isinstance(v, (int, str)) and str(v).isdigit():
                out["gbl_indexYear_im"] = [int(v)]
            else:
                out["gbl_indexYear_im"] = None

        # Array-ish fields: ensure list for Postgres array columns
        array_fields = {
            c.name
            for c in resources.c
            if hasattr(c.type, "__class__") and c.type.__class__.__name__ == "ARRAY"
        }
        for f in array_fields:
            if f not in out or out[f] is None:
                continue
            v = out[f]
            if isinstance(v, list):
                continue
            if isinstance(v, str):
                out[f] = [v] if v.strip() else None
            else:
                out[f] = [str(v)]

        # JSON-ish fields in resources table
        # - dct_references_s is stored as Text in this DB; keep it as a JSON string if dict/list
        if "dct_references_s" in out and isinstance(out["dct_references_s"], (dict, list)):
            out["dct_references_s"] = json.dumps(out["dct_references_s"])

        # - b1g_access_s is JSON column; keep dict as-is; coerce string JSON when possible
        if "b1g_access_s" in out and isinstance(out["b1g_access_s"], str):
            try:
                out["b1g_access_s"] = json.loads(out["b1g_access_s"])
            except Exception:
                pass

        # Some OGM feeds provide scalar string fields as single-item lists.
        if "dct_title_s" in out and isinstance(out["dct_title_s"], list):
            title_list = [str(v).strip() for v in out["dct_title_s"] if str(v).strip()]
            out["dct_title_s"] = title_list[0] if title_list else None

        # Some OGM feeds provide b1g_harvestWorkflow_s as a single-item list,
        # but the DB column is scalar text.
        if "b1g_harvestWorkflow_s" in out and isinstance(out["b1g_harvestWorkflow_s"], list):
            workflow_list = [str(v).strip() for v in out["b1g_harvestWorkflow_s"] if str(v).strip()]
            out["b1g_harvestWorkflow_s"] = workflow_list[0] if workflow_list else None

        publication_state = _normalize_scalar_string(out.get("publication_state"))
        b1g_publication_state = _normalize_scalar_string(out.get("b1g_publication_state_s"))
        effective_publication_state = publication_state or b1g_publication_state or "published"
        out["publication_state"] = effective_publication_state
        out["b1g_publication_state_s"] = effective_publication_state

        # Tag injection
        tags: List[str] = []
        existing = out.get("b1g_adminTags_sm")
        if isinstance(existing, list):
            tags.extend([str(t) for t in existing if t is not None])
        elif isinstance(existing, str) and existing.strip():
            tags.append(existing.strip())

        tags.append(f"ogm_repo:{repo_name}")
        if alias := derive_repo_alias(repo_name):
            tags.append(f"ogm:{alias}")

        # Deduplicate while preserving order
        seen = set()
        deduped = []
        for t in tags:
            if t and t not in seen:
                seen.add(t)
                deduped.append(t)
        out["b1g_adminTags_sm"] = deduped

        # Coerce timestamp/date columns to proper Python types for asyncpg.
        timestamp_fields = {c.name for c in resources.c if c.type.__class__.__name__ == "TIMESTAMP"}
        date_fields = {c.name for c in resources.c if c.type.__class__.__name__ == "Date"}

        for f in timestamp_fields:
            if f not in out or out[f] is None:
                continue
            v = out[f]
            # Some feeds might provide a list with a single timestamp (string or datetime).
            if isinstance(v, list):
                v = v[0] if v else None

            if v is None:
                out[f] = None
                continue

            if isinstance(v, datetime):
                # DB columns are TIMESTAMP (no tz). Ensure tz-aware -> naive UTC.
                out[f] = v.astimezone(timezone.utc).replace(tzinfo=None) if v.tzinfo else v
                continue

            if isinstance(v, str):
                out[f] = _parse_iso_datetime(v)
                continue

            # Unknown type; avoid asyncpg bind failures
            out[f] = None

        for f in date_fields:
            if f not in out or out[f] is None:
                continue
            v = out[f]
            if isinstance(v, date) and not isinstance(v, datetime):
                continue
            if isinstance(v, list) and v:
                v = v[0]
            if isinstance(v, str):
                out[f] = _parse_iso_date(v)

        return out

    async def upsert_records(
        self,
        repo_name: str,
        records: List[Tuple[Dict[str, Any], str]],
        source_commit_sha: Optional[str] = None,
    ) -> Dict[str, int]:
        """
        Upsert a batch of (record, source_path) pairs.
        Returns stats dict: processed, imported, skipped, errors.
        """
        stats = {"processed": 0, "imported": 0, "skipped": 0, "errors": 0}
        error_samples: List[Dict[str, Any]] = []
        error_signature_counts: Dict[str, int] = {}

        def _add_error_sample(stage: str, error: Exception, rid: Optional[str] = None) -> None:
            signature = f"{error.__class__.__name__}: {str(error)[:180]}"
            error_signature_counts[signature] = error_signature_counts.get(signature, 0) + 1
            if len(error_samples) >= 20:
                return
            error_samples.append({"stage": stage, "resource_id": rid, "error": str(error)[:500]})

        if not database.is_connected:
            await database.connect()

        run_started_at = datetime.utcnow()
        db_columns = await self._resource_columns_in_db()
        upsert_columns = [c for c in resources.c if c.name in db_columns]

        async with database.transaction():
            for record, source_path in records:
                stats["processed"] += 1
                try:
                    normalized = self._normalize_record(record, repo_name)
                    rid = normalized.get("id")
                    if not rid:
                        stats["skipped"] += 1
                        continue

                    # Ensure every column key exists (missing -> None) for a stable upsert payload
                    row = {c.name: normalized.get(c.name) for c in upsert_columns}

                    stmt = pg_insert(resources).values(row)
                    update_map = {
                        c.name: stmt.excluded[c.name] for c in upsert_columns if c.name != "id"
                    }
                    stmt = stmt.on_conflict_do_update(
                        index_elements=[resources.c.id], set_=update_map
                    )
                    await database.execute(stmt)

                    try:
                        await sync_distributions_for_resource(str(rid), row.get("dct_references_s"))
                    except Exception as dist_err:
                        logger.warning(
                            "Distribution sync failed for %s; continuing. err=%s",
                            rid,
                            str(dist_err),
                        )

                    try:
                        await sync_relationships_for_resource_ids([str(rid)])
                    except Exception as rel_err:
                        logger.warning(
                            "Relationship sync failed for %s; continuing. err=%s",
                            rid,
                            str(rel_err),
                        )

                    # Mark seen for missing tracking
                    await self.repo.upsert_resource_seen(
                        ogm_repo_name=repo_name,
                        ogm_resource_id=str(rid),
                        ogm_source_path=source_path,
                        ogm_source_commit_sha=source_commit_sha,
                        ogm_last_seen_at=run_started_at,
                    )
                    stats["imported"] += 1
                except Exception as e:
                    stats["errors"] += 1
                    _add_error_sample(
                        "upsert_record", e, rid=str(record.get("id")) if record else None
                    )

        # Mark missing after transaction, without building a huge NOT IN list
        await self.repo.mark_missing_stale(repo_name, run_started_at=run_started_at)

        if error_samples:
            stats["error_samples"] = error_samples
            stats["error_signatures"] = [
                {"signature": k, "count": v}
                for k, v in sorted(
                    error_signature_counts.items(), key=lambda kv: kv[1], reverse=True
                )[:10]
            ]
        return stats

    async def upsert_stream(
        self,
        repo_name: str,
        record_stream: Iterable[Tuple[Dict[str, Any], str]],
        source_commit_sha: Optional[str] = None,
        batch_size: int = 500,
        run_started_at: Optional[datetime] = None,
        ogm_run_id: Optional[int] = None,
        progress_meta: Optional[Dict[str, Any]] = None,
        progress_min_seconds: float = 5.0,
    ) -> Dict[str, int]:
        """
        Streaming import variant: consumes an iterator of (record, source_path) and upserts
        resources in batches, while also updating ogm_resource_state in batches.
        """
        stats = {"processed": 0, "imported": 0, "skipped": 0, "errors": 0}
        error_samples: List[Dict[str, Any]] = []
        error_signature_counts: Dict[str, int] = {}

        def _add_error_sample(
            stage: str,
            error: Exception,
            rid: Optional[str] = None,
            source_path: Optional[str] = None,
        ) -> None:
            signature = f"{error.__class__.__name__}: {str(error)[:180]}"
            error_signature_counts[signature] = error_signature_counts.get(signature, 0) + 1
            if len(error_samples) >= 20:
                return
            error_samples.append(
                {
                    "stage": stage,
                    "resource_id": rid,
                    "source_path": source_path,
                    "error": str(error)[:500],
                }
            )

        if not database.is_connected:
            await database.connect()

        run_started_at = run_started_at or datetime.utcnow()
        db_columns = await self._resource_columns_in_db()
        upsert_columns = [c for c in resources.c if c.name in db_columns]

        # asyncpg/Postgres has a hard limit on number of bind parameters per statement (32767).
        # Our bulk UPSERT is row_count * column_count parameters; clamp batch_size to
        # stay under the limit.
        # Use a little headroom to avoid edge cases.
        PARAM_LIMIT = 32767
        HEADROOM = 256
        col_count = len(list(resources.c))
        if col_count > 0:
            safe_max_rows = max(1, (PARAM_LIMIT - HEADROOM) // col_count)
            if batch_size > safe_max_rows:
                batch_size = safe_max_rows

        last_progress = 0.0

        async def _maybe_progress(force: bool = False) -> None:
            nonlocal last_progress
            if not ogm_run_id:
                return
            now_m = time.monotonic()
            if not force and (now_m - last_progress) < progress_min_seconds:
                return
            last_progress = now_m
            meta = progress_meta or {}
            await self.repo.update_harvest_run(
                ogm_id=int(ogm_run_id),
                ogm_stats_json={
                    "stage": "import",
                    "updated_at": datetime.utcnow().isoformat() + "Z",
                    **meta,
                    **stats,
                },
            )

        batch_rows: List[Dict[str, Any]] = []
        seen_rows: List[Dict[str, Any]] = []

        async def _flush_rows(rows: List[Dict[str, Any]], seen: List[Dict[str, Any]]) -> int:
            """
            Try a bulk upsert. If it fails, bisect to isolate bad records and continue.
            Runs each attempt inside its own transaction so one bad record doesn't poison
            the whole repo.
            """
            if not rows:
                return 0
            try:
                stmt = pg_insert(resources).values(rows)
                update_map = {
                    c.name: stmt.excluded[c.name] for c in upsert_columns if c.name != "id"
                }
                stmt = stmt.on_conflict_do_update(index_elements=[resources.c.id], set_=update_map)
                async with database.transaction():
                    await database.execute(stmt)
                    try:
                        await sync_distributions_for_batch(rows)
                    except Exception as dist_err:
                        logger.warning(
                            "Distribution sync failed for batch; continuing. err=%s",
                            str(dist_err),
                        )
                    try:
                        await sync_relationships_for_batch(rows)
                    except Exception as rel_err:
                        logger.warning(
                            "Relationship sync failed for batch; continuing. err=%s",
                            str(rel_err),
                        )
                    await self.repo.upsert_resources_seen_batch(repo_name, seen)
                return len(rows)
            except Exception as e:
                if len(rows) == 1:
                    rid = (seen[0] or {}).get("ogm_resource_id") if seen else None
                    source_path = (seen[0] or {}).get("ogm_source_path") if seen else None
                    logger.warning(
                        "OGM upsert failed for single record; skipping. repo=%s id=%s err=%s",
                        repo_name,
                        rid,
                        str(e),
                    )
                    stats["errors"] += 1
                    _add_error_sample("bulk_upsert_single", e, rid=rid, source_path=source_path)
                    return 0
                mid = len(rows) // 2
                left = await _flush_rows(rows[:mid], seen[:mid])
                right = await _flush_rows(rows[mid:], seen[mid:])
                return left + right

        async def _flush() -> None:
            nonlocal batch_rows, seen_rows
            if not batch_rows:
                return
            rows, seen = batch_rows, seen_rows
            batch_rows, seen_rows = [], []
            imported = await _flush_rows(rows, seen)
            stats["imported"] += imported
            await _maybe_progress()

        for record, source_path in record_stream:
            stats["processed"] += 1
            try:
                normalized = self._normalize_record(record, repo_name)
                rid = normalized.get("id")
                if not rid:
                    stats["skipped"] += 1
                    continue

                row = {c.name: normalized.get(c.name) for c in upsert_columns}
                batch_rows.append(row)
                seen_rows.append(
                    {
                        "ogm_resource_id": str(rid),
                        "ogm_last_seen_at": run_started_at,
                        "ogm_source_path": source_path,
                        "ogm_source_commit_sha": source_commit_sha,
                    }
                )

                # Heartbeat during long imports even before flushing a batch.
                await _maybe_progress()

                if len(batch_rows) >= batch_size:
                    await _flush()
            except Exception as e:
                logger.warning(
                    "OGM record normalization/enqueue failed; skipping. repo=%s err=%s",
                    repo_name,
                    str(e),
                )
                stats["errors"] += 1
                _add_error_sample(
                    "normalize_or_enqueue",
                    e,
                    rid=str(record.get("id")) if isinstance(record, dict) else None,
                    source_path=source_path,
                )

        # flush remaining
        await _flush()

        # final heartbeat for import stage (ensures recent timestamp even for small repos)
        await _maybe_progress(force=True)

        await self.repo.mark_missing_stale(repo_name, run_started_at=run_started_at)
        if error_samples:
            stats["error_samples"] = error_samples
            stats["error_signatures"] = [
                {"signature": k, "count": v}
                for k, v in sorted(
                    error_signature_counts.items(), key=lambda kv: kv[1], reverse=True
                )[:10]
            ]
        return stats
