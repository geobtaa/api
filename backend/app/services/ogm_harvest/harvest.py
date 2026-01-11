from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from app.services.ogm_harvest.aardvark_reader import read_aardvark_records
from app.services.ogm_harvest.dumps import OGMHarvestDumpWriter
from app.services.ogm_harvest.importer import OGMResourceImporter
from app.services.ogm_harvest.repo_sync import OGMRepoSync
from app.services.ogm_harvest.repository import OGMHarvestRepository

logger = logging.getLogger(__name__)


async def harvest_repo(
    repo_name: str,
    trigger: str = "manual",
    checkout_base_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Harvest a single OpenGeoMetadata repo into Postgres.

    Returns a dict with run_id, repo, commit, stats, and missing_count.
    """
    repo = OGMHarvestRepository()
    syncer = OGMRepoSync(base_dir=checkout_base_dir)
    importer = OGMResourceImporter(repo=repo)

    await repo.upsert_repo(ogm_repo_name=repo_name)
    await repo.mark_repo_harvest_started(repo_name)
    run_id = await repo.create_harvest_run(ogm_repo_name=repo_name, ogm_trigger=trigger)
    run_started_at = datetime.utcnow()
    # Cancel any older stuck/duplicate "running" runs for this repo so status pages stay sane.
    await repo.cancel_other_running_runs(
        repo_name, keep_ogm_id=run_id, reason=f"superseded by run {run_id}"
    )

    try:
        await repo.update_harvest_run(
            ogm_id=run_id,
            ogm_stats_json={"stage": "sync", "updated_at": datetime.utcnow().isoformat() + "Z"},
        )
        logger.info("OGM harvest_repo: syncing repo %s (run_id=%s)", repo_name, run_id)
        sync_result = await asyncio.to_thread(syncer.ensure_repo, repo_name)
        head_sha = sync_result.head_sha

        # Dump + streaming import
        dump_writer = OGMHarvestDumpWriter(repo_name=repo_name, run_id=run_id)
        record_stream = (
            (ref.record, ref.source_path) for ref in read_aardvark_records(sync_result.repo_dir)
        )

        await repo.update_harvest_run(
            ogm_id=run_id,
            ogm_stats_json={
                "stage": "import",
                "head_sha": head_sha,
                "repo_action": sync_result.action,
                "updated_at": datetime.utcnow().isoformat() + "Z",
            },
        )
        logger.info(
            "OGM harvest_repo: importing records for %s (run_id=%s head_sha=%s action=%s)",
            repo_name,
            run_id,
            head_sha,
            sync_result.action,
        )
        stats = await importer.upsert_stream(
            repo_name=repo_name,
            record_stream=record_stream,
            source_commit_sha=head_sha,
            batch_size=500,
            run_started_at=run_started_at,
            ogm_run_id=run_id,
            progress_meta={"head_sha": head_sha, "repo_action": sync_result.action},
        )
        await repo.update_harvest_run(
            ogm_id=run_id,
            ogm_stats_json={
                **(stats or {}),
                "stage": "dumps",
                "updated_at": datetime.utcnow().isoformat() + "Z",
            },
        )
        dump_paths = dump_writer.finalize(
            repo_name=repo_name,
            run_id=run_id,
            head_sha=head_sha,
            stats=stats,
        )

        await repo.finalize_harvest_run(
            ogm_id=run_id,
            ogm_status="success",
            ogm_stats_json=stats,
            ogm_dump_dir=str(dump_paths.run_dir),
        )
        await repo.mark_repo_harvest_completed(
            ogm_repo_name=repo_name,
            ogm_status="success",
            ogm_last_commit_sha=head_sha,
        )

        logger.info(
            "OGM harvest_repo: completed repo=%s run_id=%s imported=%s errors=%s dump_dir=%s",
            repo_name,
            run_id,
            stats.get("imported"),
            stats.get("errors"),
            dump_paths.run_dir,
        )
        return {
            "ogm_run_id": run_id,
            "ogm_repo_name": repo_name,
            "ogm_head_sha": head_sha,
            "ogm_repo_action": sync_result.action,
            "stats": stats,
            "ogm_dump_dir": str(dump_paths.run_dir),
        }
    except Exception as e:
        logger.error("OGM harvest failed for %s: %s", repo_name, e, exc_info=True)
        # Best-effort progress update (do not override finalize_harvest_run fields)
        try:
            await repo.update_harvest_run(
                ogm_id=run_id,
                ogm_stats_json={
                    "stage": "failed",
                    "updated_at": datetime.utcnow().isoformat() + "Z",
                },
                ogm_error=str(e),
            )
        except Exception:
            pass
        await repo.finalize_harvest_run(
            ogm_id=run_id,
            ogm_status="failed",
            ogm_error=str(e),
        )
        await repo.mark_repo_harvest_completed(
            ogm_repo_name=repo_name,
            ogm_status="failed",
            ogm_last_commit_sha=None,
        )
        raise
