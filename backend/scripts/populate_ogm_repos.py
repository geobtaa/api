#!/usr/bin/env python3
"""
Populate the ogm_repos table from GitHub org repositories.

Source of truth: https://github.com/OpenGeoMetadata

This script:
- lists repos in a GitHub org via the REST API
- checks whether each repo has a top-level `metadata-aardvark/` directory
- upserts into Postgres table `ogm_repos`
- flags repos missing aardvark via `ogm_tags["ogm_missing_aardvark"] = true`

Auth:
- optional GitHub token to avoid tight rate limits
  - env: GITHUB_TOKEN
  - or:  --github-token ...
"""

from __future__ import annotations

import argparse
import json
import os
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse, urlunparse

import requests
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import insert as pg_insert

# Keep script self-contained: import the SQLAlchemy Table definitions.
from db.models import ogm_repos


def _sync_database_url(database_url: str) -> str:
    # Convert asyncpg URL to sync URL
    sync_url = database_url.replace("postgresql+asyncpg://", "postgresql://")

    # If running locally (not in Docker) and URL points to docker hostnames, map to localhost:2345
    is_docker = os.getenv("IS_DOCKER", "false").lower() == "true"
    if not is_docker and sync_url:
        parsed = urlparse(sync_url)
        docker_hostnames = {
            "paradedb",
            "btaa-geospatial-api-paradedb",
            "btaa-geospatial-api-paradedb-1",
        }
        if parsed.hostname in docker_hostnames:
            new_netloc = f"{parsed.username}:{parsed.password}@localhost:2345"
            sync_url = urlunparse(parsed._replace(netloc=new_netloc))

    return sync_url


def _github_headers(token: Optional[str]) -> Dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "BTAA-Geospatial-Data-API/1.0",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def list_org_repos(org: str, token: Optional[str], per_page: int = 100) -> List[Dict[str, Any]]:
    repos: List[Dict[str, Any]] = []
    page = 1
    while True:
        url = f"https://api.github.com/orgs/{org}/repos"
        resp = requests.get(
            url,
            headers=_github_headers(token),
            params={"per_page": per_page, "page": page},
            timeout=30,
        )
        if resp.status_code != 200:
            raise RuntimeError(
                f"GitHub API error listing repos: {resp.status_code} {resp.text[:500]}"
            )
        batch = resp.json()
        if not isinstance(batch, list) or not batch:
            break
        repos.extend(batch)
        page += 1
    return repos


def repo_has_metadata_aardvark(
    org: str, repo_name: str, default_branch: Optional[str], token: Optional[str]
) -> bool:
    # GitHub contents API for a directory returns a JSON array (200) if present, 404 if missing.
    url = f"https://api.github.com/repos/{org}/{repo_name}/contents/metadata-aardvark"
    params = {}
    if default_branch:
        params["ref"] = default_branch
    resp = requests.get(url, headers=_github_headers(token), params=params, timeout=30)
    if resp.status_code == 200:
        body = resp.json()
        return isinstance(body, list)
    if resp.status_code == 404:
        return False
    # Treat other errors as non-fatal but recordable upstream; caller can decide.
    raise RuntimeError(
        f"GitHub API error checking metadata-aardvark for {org}/{repo_name}: "
        f"{resp.status_code} {resp.text[:500]}"
    )


def build_repo_row(repo: Dict[str, Any], *, has_aardvark: bool) -> Dict[str, Any]:
    name = repo.get("name")
    full_name = repo.get("full_name")
    default_branch = repo.get("default_branch")
    archived = bool(repo.get("archived", False))
    size_kb = repo.get("size")

    tags = {
        "ogm_repo_full_name": full_name,
        "ogm_default_branch": default_branch,
        "ogm_archived": archived,
        "ogm_size_kb": size_kb,
        "ogm_has_aardvark": bool(has_aardvark),
        "ogm_missing_aardvark": bool(not has_aardvark),
        "ogm_pushed_at": repo.get("pushed_at"),
        "ogm_updated_at": repo.get("updated_at"),
    }

    # Policy:
    # - if no aardvark directory, disable by default (so it won't be harvested)
    # - otherwise enable and default to nightly (can be edited via admin endpoint)
    ogm_enabled = bool(has_aardvark and not archived)
    ogm_watch_mode = "nightly" if ogm_enabled else "manual"

    return {
        "ogm_repo_name": name,
        "ogm_enabled": ogm_enabled,
        "ogm_watch_mode": ogm_watch_mode,
        "ogm_notes": None,
        "ogm_tags": tags,
    }


def upsert_rows(
    sync_db_url: str, rows: List[Dict[str, Any]], dry_run: bool = False
) -> Tuple[int, int]:
    if not rows:
        return (0, 0)
    engine = create_engine(sync_db_url)
    inserted = 0
    updated = 0

    with engine.begin() as conn:
        for row in rows:
            if dry_run:
                continue

            stmt = pg_insert(ogm_repos).values(**row)
            # Update mutable fields only (keep harvest timestamps/status)
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
            conn.execute(stmt)
            # We don't have a clean rowcount split for insert vs update here; treat as upserted.
            inserted += 1

    return (inserted, updated)


def main():
    parser = argparse.ArgumentParser(description="Populate ogm_repos from GitHub org repos")
    parser.add_argument(
        "--org", default="OpenGeoMetadata", help="GitHub org name (default: OpenGeoMetadata)"
    )
    parser.add_argument(
        "--github-token", default=None, help="GitHub token (or set GITHUB_TOKEN env var)"
    )
    parser.add_argument("--per-page", type=int, default=100, help="GitHub API per_page (max 100)")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of repos processed")
    parser.add_argument("--dry-run", action="store_true", help="Do not write to the database")
    parser.add_argument(
        "--include-archived",
        action="store_true",
        help="Include archived repos (default: skip archived)",
    )
    args = parser.parse_args()

    token = args.github_token or os.getenv("GITHUB_TOKEN")

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL is required in the environment for this script.")
    sync_db_url = _sync_database_url(database_url)

    repos = list_org_repos(args.org, token, per_page=args.per_page)
    if not args.include_archived:
        repos = [r for r in repos if not r.get("archived", False)]

    if args.limit:
        repos = repos[: args.limit]

    rows: List[Dict[str, Any]] = []
    missing_aardvark = 0
    processed = 0

    for repo in repos:
        name = repo.get("name")
        if not isinstance(name, str) or not name:
            continue
        default_branch = repo.get("default_branch")
        processed += 1
        try:
            has_aardvark = repo_has_metadata_aardvark(args.org, name, default_branch, token)
        except Exception as e:
            # If the check fails (rate limit, permissions), keep the repo but mark unknown.
            has_aardvark = False
            repo.setdefault("notes", str(e))

        if not has_aardvark:
            missing_aardvark += 1

        rows.append(build_repo_row(repo, has_aardvark=has_aardvark))

    upserted, _updated = upsert_rows(sync_db_url, rows, dry_run=args.dry_run)

    summary = {
        "org": args.org,
        "processed": processed,
        "upserted": upserted if not args.dry_run else 0,
        "missing_aardvark": missing_aardvark,
        "dry_run": bool(args.dry_run),
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
