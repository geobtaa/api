#!/usr/bin/env python3
# ruff: noqa: E402
"""
Nightly OpenGeoMetadata repo discovery + harvest enqueue.

This script is intended for cron or another scheduler. It does two things:

1. Refreshes the local `ogm_repos` watch list from the GitHub org.
2. Enqueues `ogm_harvest_all(trigger="nightly")` so enabled repos are harvested.

Run from the backend root, for example:

    cd backend
    python scripts/trigger_ogm_nightly_sync.py
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.tasks.ogm_harvest import ogm_harvest_all
from scripts.populate_ogm_repos import (
    _sync_database_url,
    build_repo_row,
    list_org_repos,
    repo_has_metadata_aardvark,
    upsert_rows,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Refresh ogm_repos from GitHub and enqueue a harvest-all task."
    )
    parser.add_argument(
        "--org", default="OpenGeoMetadata", help="GitHub org name (default: OpenGeoMetadata)"
    )
    parser.add_argument(
        "--github-token", default=None, help="GitHub token (or set GITHUB_TOKEN env var)"
    )
    parser.add_argument("--per-page", type=int, default=100, help="GitHub API per_page (max 100)")
    parser.add_argument("--limit", type=int, default=None, help="Limit repos processed")
    parser.add_argument(
        "--include-archived",
        action="store_true",
        help="Include archived repos when refreshing ogm_repos",
    )
    parser.add_argument(
        "--skip-harvest",
        action="store_true",
        help="Refresh the repo catalog but do not enqueue ogm_harvest_all",
    )
    parser.add_argument("--dry-run", action="store_true", help="Do not write or enqueue anything")
    args = parser.parse_args()

    token = args.github_token or os.getenv("GITHUB_TOKEN")
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL is required in the environment for this script.")

    sync_db_url = _sync_database_url(database_url)
    repos = list_org_repos(args.org, token, per_page=args.per_page)
    if not args.include_archived:
        repos = [repo for repo in repos if not repo.get("archived", False)]
    if args.limit is not None:
        repos = repos[: args.limit]

    rows: List[Dict[str, Any]] = []
    processed = 0
    enabled = 0
    missing_aardvark = 0

    for repo in repos:
        name = repo.get("name")
        if not isinstance(name, str) or not name:
            continue
        processed += 1
        default_branch = repo.get("default_branch")

        try:
            has_aardvark = repo_has_metadata_aardvark(args.org, name, default_branch, token)
        except Exception as exc:
            has_aardvark = False
            repo.setdefault("notes", str(exc))

        if not has_aardvark:
            missing_aardvark += 1

        row = build_repo_row(repo, has_aardvark=has_aardvark)
        if row["ogm_enabled"]:
            enabled += 1
        rows.append(row)

    upserted, _updated = upsert_rows(sync_db_url, rows, dry_run=args.dry_run)

    harvest_task_id = None
    if not args.dry_run and not args.skip_harvest:
        task = ogm_harvest_all.delay(trigger="nightly")
        harvest_task_id = task.id

    print(
        json.dumps(
            {
                "org": args.org,
                "processed": processed,
                "enabled": enabled,
                "missing_aardvark": missing_aardvark,
                "upserted": 0 if args.dry_run else upserted,
                "harvest_enqueued": bool(harvest_task_id),
                "harvest_task_id": harvest_task_id,
                "dry_run": bool(args.dry_run),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
