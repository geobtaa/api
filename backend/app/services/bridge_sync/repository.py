from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional, Set

from sqlalchemy import func, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from db.database import database
from db.models import bridge_resource_state, bridge_sync_runs, resources


class BridgeSyncRepository:
    """Async repository for bridge sync state and run tracking."""

    def __init__(self) -> None:
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

    async def retire_missing_resources(self, resource_ids: List[str], retired_at: datetime) -> int:
        if not resource_ids:
            return 0

        resource_columns = await self._resource_columns_in_db()
        retired_date = date.fromisoformat(retired_at.date().isoformat())
        state_stmt = (
            update(bridge_resource_state)
            .where(bridge_resource_state.c.bridge_resource_id.in_(resource_ids))
            .where(bridge_resource_state.c.bridge_retired_at.is_(None))
            .values(bridge_retired_at=retired_at, bridge_updated_at=retired_at)
            .returning(bridge_resource_state.c.bridge_resource_id)
        )
        state_rows = await database.fetch_all(state_stmt)
        retired_ids = [str(row["bridge_resource_id"]) for row in state_rows]
        if not retired_ids:
            return 0

        update_values: Dict[str, Any] = {"publication_state": "retired"}
        if "b1g_publication_state_s" in resource_columns:
            update_values["b1g_publication_state_s"] = "retired"
        if "b1g_dateRetired_dt" in resource_columns:
            update_values["b1g_dateRetired_dt"] = func.coalesce(
                resources.c.b1g_dateRetired_dt, retired_at
            )
        if "b1g_dateRetired_s" in resource_columns:
            update_values["b1g_dateRetired_s"] = func.coalesce(
                resources.c.b1g_dateRetired_s, retired_date
            )
        if "date_modified_dtsi" in resource_columns:
            update_values["date_modified_dtsi"] = retired_at

        resource_stmt = (
            update(resources).where(resources.c.id.in_(retired_ids)).values(**update_values)
        )
        await database.execute(resource_stmt)
        return len(retired_ids)
