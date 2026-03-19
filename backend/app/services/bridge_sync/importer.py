from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Set

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.services.bridge_sync.nested_sync import sync_nested_for_batch
from app.services.bridge_sync.repository import BridgeSyncRepository
from app.services.distribution_sync import (
    sync_distributions_for_batch,
    sync_document_distributions_for_batch,
)
from app.services.ogm_harvest.aardvark_reader import extract_record_id
from app.services.ogm_harvest.importer import _parse_iso_date, _parse_iso_datetime
from db.database import database
from db.models import resources

logger = logging.getLogger(__name__)


class BridgeResourceImporter:
    """Normalize bridge records and UPSERT them into `resources`."""

    def __init__(self, repo: Optional[BridgeSyncRepository] = None):
        self.repo = repo or BridgeSyncRepository()
        self._resource_columns_cache: Optional[Set[str]] = None

    async def _resource_columns_in_db(self) -> Set[str]:
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
        for row in rows:
            try:
                name = row["column_name"]
            except Exception:
                name = None
            if name:
                cols.add(str(name))
        if not cols:
            cols = {c.name for c in resources.c}
        self._resource_columns_cache = cols
        return cols

    def _normalize_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        out: Dict[str, Any] = {}

        rid = extract_record_id(record)
        if rid:
            out["id"] = str(rid)

        for col in resources.c:
            name = col.name
            if name == "id":
                continue
            if name in record:
                out[name] = record.get(name)

        if "import_id" in out and out["import_id"] is not None:
            out["import_id"] = str(out["import_id"])

        if "gbl_indexYear_im" in out:
            value = out.get("gbl_indexYear_im")
            if isinstance(value, list):
                out["gbl_indexYear_im"] = [int(v) for v in value if str(v).isdigit()] or None
            elif isinstance(value, (int, str)) and str(value).isdigit():
                out["gbl_indexYear_im"] = [int(value)]
            else:
                out["gbl_indexYear_im"] = None

        array_fields = {
            c.name
            for c in resources.c
            if hasattr(c.type, "__class__") and c.type.__class__.__name__ == "ARRAY"
        }
        for field in array_fields:
            if field not in out or out[field] is None:
                continue
            value = out[field]
            if isinstance(value, list):
                continue
            if isinstance(value, str):
                out[field] = [value] if value.strip() else None
            else:
                out[field] = [str(value)]

        if "dct_references_s" in out and isinstance(out["dct_references_s"], (dict, list)):
            out["dct_references_s"] = json.dumps(out["dct_references_s"])

        if "b1g_access_s" in out and isinstance(out["b1g_access_s"], str):
            try:
                out["b1g_access_s"] = json.loads(out["b1g_access_s"])
            except Exception:
                pass

        if "dct_title_s" in out and isinstance(out["dct_title_s"], list):
            title_list = [str(v).strip() for v in out["dct_title_s"] if str(v).strip()]
            out["dct_title_s"] = title_list[0] if title_list else None

        if "b1g_harvestWorkflow_s" in out and isinstance(out["b1g_harvestWorkflow_s"], list):
            workflow_list = [str(v).strip() for v in out["b1g_harvestWorkflow_s"] if str(v).strip()]
            out["b1g_harvestWorkflow_s"] = workflow_list[0] if workflow_list else None

        publication_state = out.get("publication_state")
        if publication_state and not out.get("b1g_publication_state_s"):
            if isinstance(publication_state, list):
                values = [str(v).strip() for v in publication_state if str(v).strip()]
                out["b1g_publication_state_s"] = values[0] if values else None
            else:
                out["b1g_publication_state_s"] = str(publication_state).strip()

        timestamp_fields = {c.name for c in resources.c if c.type.__class__.__name__ == "TIMESTAMP"}
        date_fields = {c.name for c in resources.c if c.type.__class__.__name__ == "Date"}

        for field in timestamp_fields:
            if field not in out or out[field] is None:
                continue
            value = out[field]
            if isinstance(value, list):
                value = value[0] if value else None
            if value is None:
                out[field] = None
            elif isinstance(value, datetime):
                out[field] = (
                    value.astimezone(timezone.utc).replace(tzinfo=None) if value.tzinfo else value
                )
            elif isinstance(value, str):
                out[field] = _parse_iso_datetime(value)
            else:
                out[field] = None

        for field in date_fields:
            if field not in out or out[field] is None:
                continue
            value = out[field]
            if isinstance(value, date) and not isinstance(value, datetime):
                continue
            if isinstance(value, list) and value:
                value = value[0]
            if isinstance(value, str):
                out[field] = _parse_iso_date(value)

        return out

    async def upsert_records(
        self,
        records: List[Dict[str, Any]],
        *,
        run_started_at: datetime,
        batch_size: int = 500,
    ) -> Dict[str, Any]:
        stats: Dict[str, Any] = {"processed": 0, "imported": 0, "skipped": 0, "errors": 0}
        error_samples: List[Dict[str, Any]] = []
        error_signature_counts: Dict[str, int] = {}

        def _add_error_sample(stage: str, error: Exception, rid: Optional[str] = None) -> None:
            signature = f"{error.__class__.__name__}: {str(error)[:180]}"
            error_signature_counts[signature] = error_signature_counts.get(signature, 0) + 1
            if len(error_samples) >= 20:
                return
            error_samples.append({"stage": stage, "resource_id": rid, "error": str(error)[:500]})

        if not records:
            return stats

        if not database.is_connected:
            await database.connect()

        db_columns = await self._resource_columns_in_db()
        upsert_columns = [c for c in resources.c if c.name in db_columns]

        param_limit = 32767
        headroom = 256
        col_count = len(upsert_columns)
        if col_count > 0:
            safe_max_rows = max(1, (param_limit - headroom) // col_count)
            if batch_size > safe_max_rows:
                batch_size = safe_max_rows

        batch_rows: List[Dict[str, Any]] = []
        seen_rows: List[Dict[str, Any]] = []
        nested_rows: List[Dict[str, Any]] = []

        async def _flush_rows(
            rows: List[Dict[str, Any]],
            seen: List[Dict[str, Any]],
            nested: List[Dict[str, Any]],
        ) -> int:
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
                            "Distribution sync failed for bridge batch; continuing. err=%s",
                            str(dist_err),
                        )
                    try:
                        await sync_document_distributions_for_batch(nested)
                    except Exception as doc_dist_err:
                        logger.warning(
                            "Document distribution sync failed for bridge batch; continuing. "
                            "err=%s",
                            str(doc_dist_err),
                        )
                    try:
                        await sync_nested_for_batch(nested)
                    except Exception as nested_err:
                        logger.warning(
                            "Nested bridge sync failed for batch; continuing. err=%s",
                            str(nested_err),
                        )
                    await self.repo.upsert_resources_seen_batch(seen)
                return len(rows)
            except Exception as exc:
                logger.error(
                    "Bridge upsert transaction failed for batch_size=%s; "
                    "will bisect/skip to isolate bad record. exc=%r",
                    len(rows),
                    exc,
                    exc_info=True,
                )
                if len(rows) == 1:
                    rid = (seen[0] or {}).get("bridge_resource_id") if seen else None
                    logger.warning(
                        "Bridge upsert failed for single record; skipping. id=%s err=%s",
                        rid,
                        str(exc),
                    )
                    stats["errors"] += 1
                    _add_error_sample("bulk_upsert_single", exc, rid=rid)
                    return 0

                mid = len(rows) // 2
                left = await _flush_rows(rows[:mid], seen[:mid], nested[:mid])
                right = await _flush_rows(rows[mid:], seen[mid:], nested[mid:])
                return left + right

        async def _flush() -> None:
            nonlocal batch_rows, seen_rows, nested_rows
            if not batch_rows:
                return
            rows, seen, nested = batch_rows, seen_rows, nested_rows
            batch_rows, seen_rows, nested_rows = [], [], []
            imported = await _flush_rows(rows, seen, nested)
            stats["imported"] += imported

        for record in records:
            stats["processed"] += 1
            try:
                normalized = self._normalize_record(record)
                rid = normalized.get("id")
                if not rid:
                    stats["skipped"] += 1
                    continue

                row = {c.name: normalized.get(c.name) for c in upsert_columns}
                batch_rows.append(row)
                seen_rows.append(
                    {
                        "bridge_resource_id": str(rid),
                        "bridge_source_import_id": normalized.get("import_id"),
                        "bridge_last_seen_at": run_started_at,
                    }
                )
                nested_rows.append(
                    {
                        "resource_id": str(rid),
                        "document_distributions": record.get("document_distributions") or [],
                        "document_downloads": record.get("document_downloads") or [],
                        "document_licensed_accesses": record.get("document_licensed_accesses")
                        or [],
                        "assets": record.get("assets") or [],
                    }
                )

                if len(batch_rows) >= batch_size:
                    await _flush()
            except Exception as exc:
                logger.warning("Bridge record normalization failed; skipping. err=%s", str(exc))
                stats["errors"] += 1
                _add_error_sample(
                    "normalize_or_enqueue",
                    exc,
                    rid=str(record.get("id")) if isinstance(record, dict) else None,
                )

        await _flush()

        if error_samples:
            stats["error_samples"] = error_samples
            stats["error_signatures"] = [
                {"signature": k, "count": v}
                for k, v in sorted(
                    error_signature_counts.items(), key=lambda kv: kv[1], reverse=True
                )[:10]
            ]
        return stats
