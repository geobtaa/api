from __future__ import annotations

import json
import logging
import time
from datetime import date, datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.services.ogm_harvest.aardvark_reader import extract_record_id
from app.services.ogm_harvest.repository import OGMHarvestRepository
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


class OGMResourceImporter:
    """
    Import Aardvark records into the `resources` table (UPSERT).

    - Injects repo tags into b1g_adminTags_sm (ogm_repo:<repo>, ogm:<alias>)
    - Normalizes common field types (arrays, ints, bools, JSON blobs)
    """

    def __init__(self, repo: Optional[OGMHarvestRepository] = None):
        self.repo = repo or OGMHarvestRepository()

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
        timestamp_fields = {
            c.name for c in resources.c if c.type.__class__.__name__ == "TIMESTAMP"
        }
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
        if not database.is_connected:
            await database.connect()

        run_started_at = datetime.utcnow()

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
                    row = {c.name: normalized.get(c.name) for c in resources.c}

                    stmt = pg_insert(resources).values(row)
                    update_map = {c.name: stmt.excluded[c.name] for c in resources.c if c.name != "id"}
                    stmt = stmt.on_conflict_do_update(index_elements=[resources.c.id], set_=update_map)
                    await database.execute(stmt)

                    # Mark seen for missing tracking
                    await self.repo.upsert_resource_seen(
                        ogm_repo_name=repo_name,
                        ogm_resource_id=str(rid),
                        ogm_source_path=source_path,
                        ogm_source_commit_sha=source_commit_sha,
                    )
                    stats["imported"] += 1
                except Exception:
                    stats["errors"] += 1

        # Mark missing after transaction, without building a huge NOT IN list
        await self.repo.mark_missing_stale(repo_name, run_started_at=run_started_at)

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
        if not database.is_connected:
            await database.connect()

        run_started_at = run_started_at or datetime.utcnow()

        # asyncpg/Postgres has a hard limit on number of bind parameters per statement (32767).
        # Our bulk UPSERT is row_count * column_count parameters; clamp batch_size to stay under the limit.
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
            Runs each attempt inside its own transaction so one bad record doesn't poison the whole repo.
            """
            if not rows:
                return 0
            try:
                stmt = pg_insert(resources).values(rows)
                update_map = {c.name: stmt.excluded[c.name] for c in resources.c if c.name != "id"}
                stmt = stmt.on_conflict_do_update(index_elements=[resources.c.id], set_=update_map)
                async with database.transaction():
                    await database.execute(stmt)
                    await self.repo.upsert_resources_seen_batch(repo_name, seen)
                return len(rows)
            except Exception as e:
                if len(rows) == 1:
                    rid = (seen[0] or {}).get("ogm_resource_id") if seen else None
                    logger.warning(
                        "OGM upsert failed for single record; skipping. repo=%s id=%s err=%s",
                        repo_name,
                        rid,
                        str(e),
                    )
                    stats["errors"] += 1
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

                row = {c.name: normalized.get(c.name) for c in resources.c}
                batch_rows.append(row)
                seen_rows.append(
                    {
                        "ogm_resource_id": str(rid),
                        "ogm_last_seen_at": datetime.utcnow(),
                        "ogm_source_path": source_path,
                        "ogm_source_commit_sha": source_commit_sha,
                    }
                )

                # Heartbeat during long imports even before flushing a batch.
                await _maybe_progress()

                if len(batch_rows) >= batch_size:
                    await _flush()
            except Exception as e:
                logger.warning("OGM record normalization/enqueue failed; skipping. repo=%s err=%s", repo_name, str(e))
                stats["errors"] += 1

        # flush remaining
        await _flush()

        # final heartbeat for import stage (ensures recent timestamp even for small repos)
        await _maybe_progress(force=True)

        await self.repo.mark_missing_stale(repo_name, run_started_at=run_started_at)
        return stats

