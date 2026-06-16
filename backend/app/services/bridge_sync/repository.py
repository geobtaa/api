from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import delete, func, or_, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from db.database import database
from db.models import (
    bridge_resource_state,
    bridge_sync_runs,
    generated_resource_representations,
    generated_visual_asset_links,
    resource_ai_enrichments,
    resource_allmaps,
    resource_assets,
    resource_data_dictionaries,
    resource_data_dictionary_entries,
    resource_distributions,
    resource_downloads,
    resource_licensed_accesses,
    resource_relationships,
    resource_thumbnail_state,
    resources,
)


class BridgeSyncRepository:
    """Async repository for bridge sync state and run tracking."""

    async def create_sync_run(self, bridge_trigger: str) -> int:
        stmt = (
            pg_insert(bridge_sync_runs)
            .values(
                bridge_trigger=bridge_trigger,
                bridge_started_at=datetime.utcnow(),
                bridge_status="running",
            )
            .returning(bridge_sync_runs.c.bridge_id)
        )
        run_id = await database.fetch_val(stmt)
        return int(run_id) if run_id is not None else 0

    async def finalize_sync_run(
        self,
        bridge_id: int,
        bridge_status: str,
        bridge_stats_json: Optional[Dict[str, Any]] = None,
        bridge_last_cursor: Optional[str] = None,
        bridge_error: Optional[str] = None,
    ) -> None:
        stmt = (
            update(bridge_sync_runs)
            .where(bridge_sync_runs.c.bridge_id == bridge_id)
            .values(
                bridge_completed_at=datetime.utcnow(),
                bridge_status=bridge_status,
                bridge_stats_json=bridge_stats_json,
                bridge_last_cursor=bridge_last_cursor,
                bridge_error=bridge_error,
            )
        )
        await database.execute(stmt)

    async def update_sync_run(
        self,
        bridge_id: int,
        bridge_status: Optional[str] = None,
        bridge_stats_json: Optional[Dict[str, Any]] = None,
        bridge_last_cursor: Optional[str] = None,
        bridge_error: Optional[str] = None,
    ) -> None:
        values: Dict[str, Any] = {}
        if bridge_status is not None:
            values["bridge_status"] = bridge_status
        if bridge_stats_json is not None:
            values["bridge_stats_json"] = bridge_stats_json
        if bridge_last_cursor is not None:
            values["bridge_last_cursor"] = bridge_last_cursor
        if bridge_error is not None:
            values["bridge_error"] = bridge_error
        if not values:
            return

        stmt = (
            update(bridge_sync_runs)
            .where(bridge_sync_runs.c.bridge_id == bridge_id)
            .values(**values)
        )
        await database.execute(stmt)

    async def cancel_other_running_runs(self, *, keep_bridge_id: int, reason: str) -> None:
        stmt = (
            update(bridge_sync_runs)
            .where(bridge_sync_runs.c.bridge_status == "running")
            .where(bridge_sync_runs.c.bridge_id != keep_bridge_id)
            .values(
                bridge_completed_at=datetime.utcnow(),
                bridge_status="cancelled",
                bridge_error=reason,
            )
        )
        await database.execute(stmt)

    async def cancel_all_running_runs(self, reason: str) -> int:
        """Mark all running sync runs as cancelled. Returns number of runs cancelled."""
        stmt = (
            update(bridge_sync_runs)
            .where(bridge_sync_runs.c.bridge_status == "running")
            .values(
                bridge_completed_at=datetime.utcnow(),
                bridge_status="cancelled",
                bridge_error=reason,
            )
            .returning(bridge_sync_runs.c.bridge_id)
        )
        rows = await database.fetch_all(stmt)
        return len(rows)

    async def list_sync_runs(
        self,
        bridge_status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        q = select(bridge_sync_runs).order_by(bridge_sync_runs.c.bridge_id.desc())
        if bridge_status:
            q = q.where(bridge_sync_runs.c.bridge_status == bridge_status)
        q = q.limit(limit).offset(offset)
        rows = await database.fetch_all(q)
        return [dict(r) for r in rows]

    async def get_sync_run(self, bridge_id: int) -> Optional[Dict[str, Any]]:
        row = await database.fetch_one(
            select(bridge_sync_runs).where(bridge_sync_runs.c.bridge_id == bridge_id)
        )
        return dict(row) if row else None

    async def list_resource_ids_for_batched_sync(
        self,
        *,
        resource_scope: str = "all",
        limit: Optional[int] = None,
    ) -> List[str]:
        scope = (resource_scope or "all").strip().lower()
        if scope == "all":
            q = select(resources.c.id).where(resources.c.id.is_not(None)).order_by(resources.c.id)
        elif scope == "published":
            q = (
                select(resources.c.id)
                .where(resources.c.id.is_not(None))
                .where(func.coalesce(resources.c.publication_state, "") != "retired")
                .order_by(resources.c.id)
            )
        elif scope == "bridge_active":
            q = (
                select(bridge_resource_state.c.bridge_resource_id)
                .where(bridge_resource_state.c.bridge_retired_at.is_(None))
                .order_by(bridge_resource_state.c.bridge_resource_id)
            )
        else:
            raise ValueError("resource_scope must be one of: all, published, bridge_active")

        if limit is not None:
            q = q.limit(max(0, int(limit)))

        rows = await database.fetch_all(q)
        ids: List[str] = []
        for row in rows:
            value = row[0] if hasattr(row, "__getitem__") else None
            if value:
                ids.append(str(value))
        return ids

    async def list_missing(self, limit: int = 200, offset: int = 0) -> List[Dict[str, Any]]:
        q = (
            select(bridge_resource_state)
            .where(bridge_resource_state.c.bridge_missing_since.is_not(None))
            .order_by(bridge_resource_state.c.bridge_missing_since.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = await database.fetch_all(q)
        return [dict(r) for r in rows]

    async def list_status_counts(self, runs_limit: int = 200) -> Dict[str, Any]:
        runs = await self.list_sync_runs(limit=runs_limit, offset=0)
        counts = {"running": 0, "success": 0, "failed": 0, "cancelled": 0, "other": 0}
        for run in runs:
            status = (run.get("bridge_status") or "").lower()
            if status in counts:
                counts[status] += 1
            else:
                counts["other"] += 1

        missing_count = await database.fetch_val(
            select(func.count())
            .select_from(bridge_resource_state)
            .where(bridge_resource_state.c.bridge_missing_since.is_not(None))
        )
        active_missing_count = await database.fetch_val(
            select(func.count())
            .select_from(bridge_resource_state)
            .where(bridge_resource_state.c.bridge_missing_since.is_not(None))
            .where(bridge_resource_state.c.bridge_retired_at.is_(None))
        )
        return {
            "counts_last_runs": counts,
            "missing_count": int(missing_count or 0),
            "active_missing_count": int(active_missing_count or 0),
            "running_runs": [
                r for r in runs if (r.get("bridge_status") or "").lower() == "running"
            ],
        }

    @staticmethod
    def _stats_processed_total(run: Dict[str, Any]) -> Optional[int]:
        stats = run.get("bridge_stats_json") or {}
        if not isinstance(stats, dict):
            return None
        value = stats.get("processed")
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _is_full_sync_run(run: Dict[str, Any]) -> bool:
        stats = run.get("bridge_stats_json") or {}
        if not isinstance(stats, dict):
            return True
        return not stats.get("resource_id") and not stats.get("changed_since")

    async def estimate_full_sync_total(
        self, recent_limit: int = 100
    ) -> Tuple[Optional[int], Optional[str]]:
        runs = await self.list_sync_runs(limit=recent_limit, offset=0)
        for run in runs:
            if (run.get("bridge_status") or "").lower() != "success":
                continue
            if not self._is_full_sync_run(run):
                continue
            processed = self._stats_processed_total(run)
            if processed and processed > 0:
                return processed, "last_successful_full_run"

        active_count = await database.fetch_val(
            select(func.count())
            .select_from(bridge_resource_state)
            .where(bridge_resource_state.c.bridge_retired_at.is_(None))
        )
        if active_count:
            return int(active_count), "active_bridge_resource_state"
        return None, None

    async def upsert_resources_seen_batch(self, items: List[Dict[str, Any]]) -> int:
        if not items:
            return 0

        now = datetime.utcnow()
        rows = []
        for item in items:
            rid = item.get("bridge_resource_id")
            if not rid:
                continue
            rows.append(
                {
                    "bridge_resource_id": str(rid),
                    "bridge_source_import_id": item.get("bridge_source_import_id"),
                    "bridge_first_seen_at": now,
                    "bridge_last_seen_at": item.get("bridge_last_seen_at") or now,
                    "bridge_missing_since": None,
                    "bridge_retired_at": None,
                    "bridge_updated_at": now,
                }
            )
        if not rows:
            return 0

        stmt = pg_insert(bridge_resource_state).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=[bridge_resource_state.c.bridge_resource_id],
            set_={
                "bridge_source_import_id": stmt.excluded.bridge_source_import_id,
                "bridge_last_seen_at": stmt.excluded.bridge_last_seen_at,
                "bridge_missing_since": None,
                "bridge_retired_at": None,
                "bridge_updated_at": stmt.excluded.bridge_updated_at,
            },
        )
        await database.execute(stmt)
        return len(rows)

    async def mark_resources_missing(
        self,
        resource_ids: List[str],
        *,
        missing_since: datetime,
    ) -> int:
        rows = []
        for resource_id in resource_ids:
            rid = str(resource_id or "").strip()
            if not rid:
                continue
            rows.append(
                {
                    "bridge_resource_id": rid,
                    "bridge_first_seen_at": missing_since,
                    "bridge_last_seen_at": missing_since,
                    "bridge_missing_since": missing_since,
                    "bridge_retired_at": None,
                    "bridge_updated_at": missing_since,
                }
            )
        if not rows:
            return 0

        stmt = pg_insert(bridge_resource_state).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=[bridge_resource_state.c.bridge_resource_id],
            set_={
                "bridge_missing_since": stmt.excluded.bridge_missing_since,
                "bridge_updated_at": stmt.excluded.bridge_updated_at,
            },
        )
        await database.execute(stmt)
        return len(rows)

    async def delete_missing_resources(self, resource_ids: List[str]) -> int:
        ids = list(dict.fromkeys(str(resource_id or "").strip() for resource_id in resource_ids))
        ids = [resource_id for resource_id in ids if resource_id]
        if not ids:
            return 0

        async with database.transaction():
            state_rows = await database.fetch_all(
                select(bridge_resource_state.c.bridge_resource_id).where(
                    bridge_resource_state.c.bridge_resource_id.in_(ids)
                )
            )
            resource_rows = await database.fetch_all(
                select(resources.c.id, resources.c.import_id).where(resources.c.id.in_(ids))
            )

            eligible_ids = {str(row["bridge_resource_id"]) for row in state_rows}
            eligible_ids.update(
                str(row["id"])
                for row in resource_rows
                if str(row["id"] or "").strip() and str(row["import_id"] or "").strip()
            )
            if not eligible_ids:
                return 0

            target_ids = list(eligible_ids)
            dictionary_rows = await database.fetch_all(
                select(resource_data_dictionaries.c.id).where(
                    resource_data_dictionaries.c.resource_id.in_(target_ids)
                )
            )
            dictionary_ids = [row["id"] for row in dictionary_rows]
            if dictionary_ids:
                await database.execute(
                    delete(resource_data_dictionary_entries).where(
                        resource_data_dictionary_entries.c.resource_data_dictionary_id.in_(
                            dictionary_ids
                        )
                    )
                )

            for table in (
                resource_ai_enrichments,
                resource_allmaps,
                resource_assets,
                resource_data_dictionaries,
                resource_distributions,
                resource_downloads,
                resource_licensed_accesses,
                resource_thumbnail_state,
                generated_resource_representations,
                generated_visual_asset_links,
            ):
                await database.execute(delete(table).where(table.c.resource_id.in_(target_ids)))

            await database.execute(
                delete(resource_relationships).where(
                    or_(
                        resource_relationships.c.subject_id.in_(target_ids),
                        resource_relationships.c.object_id.in_(target_ids),
                    )
                )
            )

            deleted_rows = await database.fetch_all(
                delete(resources).where(resources.c.id.in_(target_ids)).returning(resources.c.id)
            )
            await database.execute(
                delete(bridge_resource_state).where(
                    bridge_resource_state.c.bridge_resource_id.in_(target_ids)
                )
            )
            return len(deleted_rows)

    async def record_batched_batch_result(
        self,
        *,
        bridge_id: int,
        batch_stats: Dict[str, Any],
        batch_number: Optional[int] = None,
        task_id: Optional[str] = None,
        failed: bool = False,
    ) -> Dict[str, Any]:
        async with database.transaction():
            row = await database.fetch_one(
                text(
                    """
                    SELECT bridge_status, bridge_stats_json
                    FROM bridge_sync_runs
                    WHERE bridge_id = :bridge_id
                    FOR UPDATE
                    """
                ).bindparams(bridge_id=bridge_id),
            )
            if row is None:
                raise ValueError(f"Bridge sync run {bridge_id} was not found")

            current_status = str(row["bridge_status"] or "").lower()
            stats = self._coerce_stats_json(row["bridge_stats_json"])
            if current_status != "running":
                return stats

            for key in (
                "processed",
                "imported",
                "skipped",
                "errors",
                "missing",
                "deleted",
                "retired",
            ):
                stats[key] = int(stats.get(key) or 0) + int(batch_stats.get(key) or 0)
            for key in ("fetch_5xx_retries",):
                if key in batch_stats:
                    stats[key] = int(stats.get(key) or 0) + int(batch_stats.get(key) or 0)
            if batch_stats.get("fetch_5xx_retry_statuses"):
                retry_statuses = dict(stats.get("fetch_5xx_retry_statuses") or {})
                for status_code, count in batch_stats.get("fetch_5xx_retry_statuses", {}).items():
                    status_key = str(status_code)
                    retry_statuses[status_key] = int(retry_statuses.get(status_key) or 0) + int(
                        count or 0
                    )
                stats["fetch_5xx_retry_statuses"] = retry_statuses
            if batch_stats.get("fetch_5xx_retry_samples"):
                retry_samples = list(stats.get("fetch_5xx_retry_samples") or [])
                for sample in batch_stats.get("fetch_5xx_retry_samples") or []:
                    if len(retry_samples) >= 20:
                        break
                    retry_samples.append(sample)
                stats["fetch_5xx_retry_samples"] = retry_samples
            for refresh_key in ("search_index_refresh", "cache_refresh"):
                if isinstance(batch_stats.get(refresh_key), dict):
                    stats[refresh_key] = self._merge_refresh_stats(
                        stats.get(refresh_key),
                        batch_stats[refresh_key],
                    )

            if failed:
                stats["batches_failed"] = int(stats.get("batches_failed") or 0) + 1
            else:
                stats["batches_completed"] = int(stats.get("batches_completed") or 0) + 1

            total_batches = int(stats.get("total_batches") or batch_stats.get("total_batches") or 0)
            batches_completed = int(stats.get("batches_completed") or 0)
            batches_failed = int(stats.get("batches_failed") or 0)
            batches_finished = batches_completed + batches_failed
            stats["batches_finished"] = batches_finished
            stats["stage"] = "batching"
            stats["updated_at"] = datetime.utcnow().isoformat() + "Z"
            stats["last_batch"] = {
                "batch_number": batch_number,
                "task_id": task_id,
                "failed": failed,
                "processed": int(batch_stats.get("processed") or 0),
                "imported": int(batch_stats.get("imported") or 0),
                "errors": int(batch_stats.get("errors") or 0),
                "missing": int(batch_stats.get("missing") or 0),
                "deleted": int(batch_stats.get("deleted") or 0),
                "retired": int(batch_stats.get("retired") or 0),
                "fetch_5xx_retries": int(batch_stats.get("fetch_5xx_retries") or 0),
            }

            self._merge_error_stats(stats, batch_stats)

            values: Dict[str, Any] = {"bridge_stats_json": stats}
            if total_batches and batches_finished >= total_batches:
                total_errors = int(stats.get("errors") or 0)
                final_status = "failed" if batches_failed or total_errors else "success"
                stats["stage"] = "failed" if final_status == "failed" else "complete"
                values.update(
                    {
                        "bridge_completed_at": datetime.utcnow(),
                        "bridge_status": final_status,
                    }
                )
                if batches_failed:
                    values["bridge_error"] = f"{batches_failed} bridge sync batch task(s) failed"
                elif total_errors:
                    values["bridge_error"] = (
                        f"bridge sync completed with {total_errors} record error(s)"
                    )

            await database.execute(
                update(bridge_sync_runs)
                .where(bridge_sync_runs.c.bridge_id == bridge_id)
                .values(**values)
            )
            return stats

    async def record_batched_batches_queued(
        self,
        *,
        bridge_id: int,
        batches_queued: int,
        queued_task_ids_sample: Optional[List[str]] = None,
        stage: str = "queueing",
    ) -> Dict[str, Any]:
        async with database.transaction():
            row = await database.fetch_one(
                text(
                    """
                    SELECT bridge_status, bridge_stats_json
                    FROM bridge_sync_runs
                    WHERE bridge_id = :bridge_id
                    FOR UPDATE
                    """
                ).bindparams(bridge_id=bridge_id),
            )
            if row is None:
                raise ValueError(f"Bridge sync run {bridge_id} was not found")

            stats = self._coerce_stats_json(row["bridge_stats_json"])
            if str(row["bridge_status"] or "").lower() != "running":
                return stats

            stats["stage"] = stage
            stats["batches_queued"] = int(batches_queued)
            stats["updated_at"] = datetime.utcnow().isoformat() + "Z"
            if queued_task_ids_sample is not None:
                stats["queued_task_ids_sample"] = queued_task_ids_sample[:20]

            await database.execute(
                update(bridge_sync_runs)
                .where(bridge_sync_runs.c.bridge_id == bridge_id)
                .values(bridge_stats_json=stats)
            )
            return stats

    @staticmethod
    def _coerce_stats_json(value: Any) -> Dict[str, Any]:
        if isinstance(value, dict):
            return dict(value)
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                return {}
            return dict(parsed) if isinstance(parsed, dict) else {}
        return {}

    @staticmethod
    def _merge_error_stats(stats: Dict[str, Any], batch_stats: Dict[str, Any]) -> None:
        samples = list(stats.get("error_samples") or [])
        for sample in batch_stats.get("error_samples") or []:
            if len(samples) >= 20:
                break
            samples.append(sample)
        if samples:
            stats["error_samples"] = samples

        counts: Dict[str, int] = {}
        for item in stats.get("error_signatures") or []:
            signature = item.get("signature") if isinstance(item, dict) else None
            if signature:
                counts[str(signature)] = counts.get(str(signature), 0) + int(item.get("count") or 0)
        for item in batch_stats.get("error_signatures") or []:
            signature = item.get("signature") if isinstance(item, dict) else None
            if signature:
                counts[str(signature)] = counts.get(str(signature), 0) + int(item.get("count") or 0)
        if counts:
            stats["error_signatures"] = [
                {"signature": signature, "count": count}
                for signature, count in sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[
                    :10
                ]
            ]

    @staticmethod
    def _merge_refresh_stats(existing: Any, update: Dict[str, Any]) -> Dict[str, Any]:
        merged: Dict[str, Any] = dict(existing) if isinstance(existing, dict) else {}
        for key, value in update.items():
            if key == "enabled":
                merged[key] = bool(merged.get(key, True)) and bool(value)
            elif key == "batch_size":
                merged[key] = value
            elif isinstance(value, bool):
                merged[key] = value
            elif isinstance(value, (int, float)):
                merged[key] = int(merged.get(key) or 0) + value
            elif isinstance(value, dict):
                merged[key] = BridgeSyncRepository._merge_refresh_stats(
                    merged.get(key),
                    value,
                )
            elif key not in merged:
                merged[key] = value
            else:
                merged[key] = value
        return merged

    async def mark_missing_stale(self, run_started_at: datetime) -> List[str]:
        now = datetime.utcnow()
        stmt = (
            update(bridge_resource_state)
            .where(bridge_resource_state.c.bridge_last_seen_at < run_started_at)
            .where(bridge_resource_state.c.bridge_missing_since.is_(None))
            .values(bridge_missing_since=now, bridge_updated_at=now)
            .returning(bridge_resource_state.c.bridge_resource_id)
        )
        rows = await database.fetch_all(stmt)
        return [str(row["bridge_resource_id"]) for row in rows]
