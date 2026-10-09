#!/usr/bin/env python3
"""Resumable thumbnail capture using the application's shared pipeline."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.api.v1.utils import _get_thumbnail_asset_url, sanitize_for_json  # noqa: E402
from app.services.distribution_repository import (  # noqa: E402
    async_session_factory,
    fetch_distribution_context,
)
from app.services.image_service import ImageService  # noqa: E402
from app.services.thumbnail_capture import capture_thumbnail  # noqa: E402
from app.services.thumbnail_state_service import (  # noqa: E402
    ThumbnailState,
    ThumbnailStatePayload,
    infer_source_type,
    safe_record_thumbnail_state,
)
from app.services.visual_asset_cache import durable_visual_asset_enabled  # noqa: E402
from app.tasks.worker import redis_client  # noqa: E402
from db.models import resources  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def _count_resources(resource_ids: list[str]) -> int:
    async with async_session_factory() as session:
        if resource_ids:
            stmt = (
                select(func.count()).select_from(resources).where(resources.c.id.in_(resource_ids))
            )
        else:
            stmt = select(func.count()).select_from(resources)
        result = await session.execute(stmt)
        return int(result.scalar_one() or 0)


async def _fetch_resources_by_ids(resource_ids: list[str]) -> list[dict[str, Any]]:
    if not resource_ids:
        return []

    async with async_session_factory() as session:
        stmt = select(resources).where(resources.c.id.in_(resource_ids)).order_by(resources.c.id)
        result = await session.execute(stmt)
        return [sanitize_for_json(dict(row._mapping)) for row in result.fetchall()]


async def _fetch_resource_batch(last_id: str | None, batch_size: int) -> list[dict[str, Any]]:
    async with async_session_factory() as session:
        stmt = select(resources).order_by(resources.c.id).limit(batch_size)
        if last_id is not None:
            stmt = stmt.where(resources.c.id > last_id)
        result = await session.execute(stmt)
        return [sanitize_for_json(dict(row._mapping)) for row in result.fetchall()]


async def _prime_thumbnail_for_resource(
    resource_dict: dict[str, Any], *, force: bool, **_unused
) -> tuple[str, str, str]:
    resource_id = str(resource_dict["id"])
    if resource_dict.get("dct_accessrights_s") == "Restricted":
        return "skipped-restricted", resource_id, "Restricted resource"
    source_url = None
    try:
        context = await fetch_distribution_context(resource_id)
        service = ImageService(resource_dict, distribution_context=context)
        # Source selection during a bulk run must not enqueue a second capture.
        service._queue_manifest_processing = lambda _url: None
        source_url = service.resolve_thumbnail_source_url(
            thumbnail_asset_url=await _get_thumbnail_asset_url(resource_id)
        )
        if not source_url:
            return "skipped-no-source", resource_id, "No thumbnail source"
        result = await asyncio.to_thread(
            capture_thumbnail, source_url, resource_id, cache=redis_client, force=force
        )
        if result.status == "deferred":
            return "deferred", resource_id, result.detail
        await safe_record_thumbnail_state(
            ThumbnailStatePayload(
                resource_id=resource_id,
                state=ThumbnailState.SUCCESS,
                source_type=infer_source_type(source_url),
                source_url=source_url,
                source_hash=result.image_hash,
                state_detail=result.detail,
            )
        )
        return result.status, resource_id, result.detail
    except Exception as exc:
        await safe_record_thumbnail_state(
            ThumbnailStatePayload(
                resource_id=resource_id,
                state=ThumbnailState.FAILURE,
                source_url=source_url,
                last_error=str(exc),
                state_detail="Capture failed",
            )
        )
        return "failed", resource_id, str(exc)


class RunJournal:
    """Append and fsync each result so interruption never loses the retry list."""

    def __init__(self, path: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.file = self.path.open("a", encoding="utf-8")

    def write(self, **record):
        self.file.write(json.dumps(record) + "\n")
        self.file.flush()
        os.fsync(self.file.fileno())

    def close(self):
        self.file.close()


def resume_scope(path: str) -> dict:
    with open(path, encoding="utf-8") as file:
        for line in file:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue  # A final interrupted write need not invalidate the run.
            if record.get("event") == "scope":
                return record
    raise ValueError("Resume journal has no scope record")


async def _process_batch(batch, *, concurrency, force, counters, journal, progress):
    semaphore = asyncio.Semaphore(concurrency)

    async def one(resource):
        async with semaphore:
            return await _prime_thumbnail_for_resource(resource, force=force)

    for resource in batch:
        journal.write(event="pending", resource_id=resource["id"])
    tasks = [asyncio.create_task(one(resource)) for resource in batch]
    try:
        for future in asyncio.as_completed(tasks):
            status, resource_id, detail = await future
            journal.write(event="result", resource_id=resource_id, status=status, detail=detail)
            counters[status] += 1
            progress.update(1)
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


async def _run(args) -> int:
    if not durable_visual_asset_enabled():
        raise ValueError("Bulk capture requires durable visual storage")
    if args.resume_report:
        if args.force or args.resource_ids:
            raise ValueError("Resume cannot be combined with --force or explicit IDs")
        scope = resume_scope(args.resume_report)
        args.resource_ids, args.limit = scope["resource_ids"], scope["limit"]
    report = (
        args.report_file
        or args.resume_report
        or (
            "logs/thumbnail-run-"
            + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            + ".jsonl"
        )
    )
    if args.report_file and Path(report).exists() and report != args.resume_report:
        raise ValueError("Report already exists; use --resume-report or a new path")
    journal = RunJournal(report)
    counters = Counter()
    logger.info("Thumbnail journal: %s", report)
    journal.write(event="scope", resource_ids=args.resource_ids, limit=args.limit)
    total = await _count_resources(args.resource_ids)
    if args.limit is not None:
        total = min(total, args.limit)
    try:
        with tqdm(total=total, desc="Thumbnails") as progress:
            if args.resource_ids:
                rows = await _fetch_resources_by_ids(args.resource_ids)
                missing = set(args.resource_ids) - {str(row["id"]) for row in rows}
                for resource_id in sorted(missing):
                    journal.write(
                        event="result",
                        resource_id=resource_id,
                        status="failed",
                        detail="Resource not found",
                    )
                    counters["failed"] += 1
                if args.limit is not None:
                    rows = rows[: args.limit]
                batches = [
                    rows[i : i + args.batch_size] for i in range(0, len(rows), args.batch_size)
                ]
                for batch in batches:
                    await _process_batch(
                        batch,
                        concurrency=args.concurrency,
                        force=args.force,
                        counters=counters,
                        journal=journal,
                        progress=progress,
                    )
            else:
                last_id, processed = None, 0
                while processed < total:
                    batch = await _fetch_resource_batch(
                        last_id, min(args.batch_size, total - processed)
                    )
                    if not batch:
                        break
                    await _process_batch(
                        batch,
                        concurrency=args.concurrency,
                        force=args.force,
                        counters=counters,
                        journal=journal,
                        progress=progress,
                    )
                    last_id, processed = str(batch[-1]["id"]), processed + len(batch)
        incomplete = bool(counters["failed"] or counters["deferred"])
        journal.write(event="summary", counts=dict(counters), complete=not incomplete)
        logger.info("Thumbnail results: %s; journal: %s", dict(counters), report)
        return int(incomplete)
    finally:
        journal.close()


def _parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("resource_ids", nargs="*")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument(
        "--force", action="store_true", help="Refresh providers; publish new byte hashes"
    )
    parser.add_argument("--report-file", help="JSONL journal path on persistent storage")
    parser.add_argument("--resume-report", help="Resume original scope, verifying stored successes")
    # Compatibility: failures are always retried and unfinished runs always fail.
    parser.add_argument("--retry-failures", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--retry-placeheld", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--strict-failures", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.batch_size < 1 or args.concurrency < 1 or (args.limit is not None and args.limit < 1):
        parser.error("Batch size, concurrency and limit must be positive")
    return args


def main():
    raise SystemExit(asyncio.run(_run(_parse_args())))


if __name__ == "__main__":
    main()
