from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from db.database import database
from db.models import ogm_harvest_runs, ogm_repos, ogm_resource_state


class OGMHarvestRepository:
    """
    Minimal async repository for OGM harvest tables.

    This intentionally uses the app-wide `db.database.database` (databases/asyncpg)
    to match the rest of the backend.
    """

    async def list_repos(self) -> List[Dict[str, Any]]:
        rows = await database.fetch_all(select(ogm_repos).order_by(ogm_repos.c.ogm_repo_name))
        return [dict(r) for r in rows]

    async def get_repo(self, ogm_repo_name: str) -> Optional[Dict[str, Any]]:
        row = await database.fetch_one(
            select(ogm_repos).where(ogm_repos.c.ogm_repo_name == ogm_repo_name)
        )
        return dict(row) if row else None

    async def upsert_repo(
        self,
        ogm_repo_name: str,
        ogm_enabled: bool = True,
        ogm_watch_mode: str = "weekly",
        ogm_notes: Optional[str] = None,
        ogm_tags: Optional[Dict[str, Any]] = None,
    ) -> None:
        stmt = pg_insert(ogm_repos).values(
            ogm_repo_name=ogm_repo_name,
            ogm_enabled=ogm_enabled,
            ogm_watch_mode=ogm_watch_mode,
            ogm_notes=ogm_notes,
            ogm_tags=ogm_tags,
            ogm_updated_at=datetime.utcnow(),
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[ogm_repos.c.ogm_repo_name],
            set_={
                "ogm_enabled": stmt.excluded.ogm_enabled,
                "ogm_watch_mode": stmt.excluded.ogm_watch_mode,
                "ogm_notes": stmt.excluded.ogm_notes,
                "ogm_tags": stmt.excluded.ogm_tags,
                "ogm_updated_at": stmt.excluded.ogm_updated_at,
            },
        )
        await database.execute(stmt)

    async def create_harvest_run(
        self,
        ogm_repo_name: str,
        ogm_trigger: str,
    ) -> int:
        stmt = (
            pg_insert(ogm_harvest_runs)
            .values(
                ogm_repo_name=ogm_repo_name,
                ogm_trigger=ogm_trigger,
                ogm_started_at=datetime.utcnow(),
                ogm_status="running",
            )
            .returning(ogm_harvest_runs.c.ogm_id)
        )
        run_id = await database.fetch_val(stmt)
        return int(run_id) if run_id is not None else 0

    async def finalize_harvest_run(
        self,
        ogm_id: int,
        ogm_status: str,
        ogm_stats_json: Optional[Dict[str, Any]] = None,
        ogm_dump_dir: Optional[str] = None,
        ogm_error: Optional[str] = None,
    ) -> None:
        stmt = (
            update(ogm_harvest_runs)
            .where(ogm_harvest_runs.c.ogm_id == ogm_id)
            .values(
                ogm_completed_at=datetime.utcnow(),
                ogm_status=ogm_status,
                ogm_stats_json=ogm_stats_json,
                ogm_dump_dir=ogm_dump_dir,
                ogm_error=ogm_error,
            )
        )
        await database.execute(stmt)

    async def update_harvest_run(
        self,
        ogm_id: int,
        ogm_status: Optional[str] = None,
        ogm_stats_json: Optional[Dict[str, Any]] = None,
        ogm_dump_dir: Optional[str] = None,
        ogm_error: Optional[str] = None,
    ) -> None:
        """
        Update an in-progress harvest run without marking it completed.
        Use this to emit progress/stage information that can be surfaced via the admin API.
        """
        values: Dict[str, Any] = {}
        if ogm_status is not None:
            values["ogm_status"] = ogm_status
        if ogm_stats_json is not None:
            values["ogm_stats_json"] = ogm_stats_json
        if ogm_dump_dir is not None:
            values["ogm_dump_dir"] = ogm_dump_dir
        if ogm_error is not None:
            values["ogm_error"] = ogm_error
        if not values:
            return
        stmt = update(ogm_harvest_runs).where(ogm_harvest_runs.c.ogm_id == ogm_id).values(**values)
        await database.execute(stmt)

    async def cancel_other_running_runs(
        self,
        ogm_repo_name: str,
        *,
        keep_ogm_id: int,
        reason: str,
    ) -> int:
        """
        If we enqueue/trigger multiple harvests for the same repo (or a worker restarts mid-run),
        older runs can remain stuck in 'running'. This cancels all other running runs for that repo.
        """
        now = datetime.utcnow()
        stmt = (
            update(ogm_harvest_runs)
            .where(ogm_harvest_runs.c.ogm_repo_name == ogm_repo_name)
            .where(ogm_harvest_runs.c.ogm_status == "running")
            .where(ogm_harvest_runs.c.ogm_id != keep_ogm_id)
            .values(
                ogm_completed_at=now,
                ogm_status="cancelled",
                ogm_error=reason,
            )
        )
        return await database.execute(stmt)

    async def list_harvest_runs(
        self,
        ogm_repo_name: Optional[str] = None,
        ogm_status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        q = select(ogm_harvest_runs).order_by(ogm_harvest_runs.c.ogm_id.desc())
        if ogm_repo_name:
            q = q.where(ogm_harvest_runs.c.ogm_repo_name == ogm_repo_name)
        if ogm_status:
            q = q.where(ogm_harvest_runs.c.ogm_status == ogm_status)
        q = q.limit(limit).offset(offset)
        rows = await database.fetch_all(q)
        return [dict(r) for r in rows]

    async def get_harvest_run(self, ogm_id: int) -> Optional[Dict[str, Any]]:
        row = await database.fetch_one(
            select(ogm_harvest_runs).where(ogm_harvest_runs.c.ogm_id == ogm_id)
        )
        return dict(row) if row else None

    async def list_missing_for_repo(
        self,
        ogm_repo_name: str,
        limit: int = 200,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        q = (
            select(ogm_resource_state)
            .where(ogm_resource_state.c.ogm_repo_name == ogm_repo_name)
            .where(ogm_resource_state.c.ogm_missing_since.is_not(None))
            .order_by(ogm_resource_state.c.ogm_missing_since.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = await database.fetch_all(q)
        return [dict(r) for r in rows]

    async def mark_repo_harvest_started(self, ogm_repo_name: str) -> None:
        stmt = (
            update(ogm_repos)
            .where(ogm_repos.c.ogm_repo_name == ogm_repo_name)
            .values(
                ogm_last_harvest_started_at=datetime.utcnow(),
                ogm_last_harvest_status="running",
                ogm_updated_at=datetime.utcnow(),
            )
        )
        await database.execute(stmt)

    async def mark_repo_harvest_completed(
        self,
        ogm_repo_name: str,
        ogm_status: str,
        ogm_last_commit_sha: Optional[str] = None,
    ) -> None:
        stmt = (
            update(ogm_repos)
            .where(ogm_repos.c.ogm_repo_name == ogm_repo_name)
            .values(
                ogm_last_harvest_completed_at=datetime.utcnow(),
                ogm_last_harvest_status=ogm_status,
                ogm_last_commit_sha=ogm_last_commit_sha,
                ogm_updated_at=datetime.utcnow(),
            )
        )
        await database.execute(stmt)

    async def upsert_resource_seen(
        self,
        ogm_repo_name: str,
        ogm_resource_id: str,
        ogm_source_path: Optional[str] = None,
        ogm_source_commit_sha: Optional[str] = None,
    ) -> None:
        now = datetime.utcnow()
        stmt = pg_insert(ogm_resource_state).values(
            ogm_repo_name=ogm_repo_name,
            ogm_resource_id=ogm_resource_id,
            ogm_first_seen_at=now,
            ogm_last_seen_at=now,
            ogm_missing_since=None,
            ogm_source_path=ogm_source_path,
            ogm_source_commit_sha=ogm_source_commit_sha,
            ogm_updated_at=now,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[
                ogm_resource_state.c.ogm_repo_name,
                ogm_resource_state.c.ogm_resource_id,
            ],
            set_={
                "ogm_last_seen_at": stmt.excluded.ogm_last_seen_at,
                "ogm_missing_since": None,
                "ogm_source_path": stmt.excluded.ogm_source_path,
                "ogm_source_commit_sha": stmt.excluded.ogm_source_commit_sha,
                "ogm_updated_at": stmt.excluded.ogm_updated_at,
            },
        )
        await database.execute(stmt)

    async def upsert_resources_seen_batch(
        self,
        ogm_repo_name: str,
        items: List[Dict[str, Any]],
    ) -> int:
        """
        Batch upsert into ogm_resource_state.

        Each item should include:
          - ogm_resource_id (required)
          - ogm_last_seen_at (required)
          - ogm_source_path, ogm_source_commit_sha (optional)
        """
        if not items:
            return 0
        now = datetime.utcnow()
        rows = []
        for it in items:
            rid = it.get("ogm_resource_id")
            if not rid:
                continue
            rows.append(
                {
                    "ogm_repo_name": ogm_repo_name,
                    "ogm_resource_id": str(rid),
                    "ogm_first_seen_at": now,
                    "ogm_last_seen_at": it.get("ogm_last_seen_at") or now,
                    "ogm_missing_since": None,
                    "ogm_source_path": it.get("ogm_source_path"),
                    "ogm_source_commit_sha": it.get("ogm_source_commit_sha"),
                    "ogm_updated_at": now,
                }
            )
        if not rows:
            return 0

        stmt = pg_insert(ogm_resource_state).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=[
                ogm_resource_state.c.ogm_repo_name,
                ogm_resource_state.c.ogm_resource_id,
            ],
            set_={
                "ogm_last_seen_at": stmt.excluded.ogm_last_seen_at,
                "ogm_missing_since": None,
                "ogm_source_path": stmt.excluded.ogm_source_path,
                "ogm_source_commit_sha": stmt.excluded.ogm_source_commit_sha,
                "ogm_updated_at": stmt.excluded.ogm_updated_at,
            },
        )
        await database.execute(stmt)
        return len(rows)

    async def mark_missing_stale(
        self,
        ogm_repo_name: str,
        run_started_at: datetime,
    ) -> int:
        """
        Mark resources as missing for a repo when their ogm_last_seen_at is older than
        the current run's start timestamp.
        """
        now = datetime.utcnow()
        stmt = (
            update(ogm_resource_state)
            .where(ogm_resource_state.c.ogm_repo_name == ogm_repo_name)
            .where(ogm_resource_state.c.ogm_last_seen_at < run_started_at)
            .where(ogm_resource_state.c.ogm_missing_since.is_(None))
            .values(ogm_missing_since=now, ogm_updated_at=now)
            .returning(ogm_resource_state.c.ogm_resource_id)
        )
        rows = await database.fetch_all(stmt)
        return len(rows)
