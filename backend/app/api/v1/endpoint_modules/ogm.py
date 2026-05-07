from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.api.v1.utils import create_response
from app.services.ogm_harvest.repository import OGMHarvestRepository

router = APIRouter()
ogm_repo = OGMHarvestRepository()
TEMPLATES_DIR = Path(__file__).resolve().parents[4] / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR)) if TEMPLATES_DIR.exists() else None


def _format_timestamp(value: Any) -> Optional[str]:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M UTC")
    if isinstance(value, str):
        try:
            normalized = value.replace("Z", "+00:00")
            parsed = datetime.fromisoformat(normalized)
            return parsed.strftime("%Y-%m-%d %H:%M UTC")
        except ValueError:
            return value
    return str(value)


@router.get("/ogm/repos")
async def list_public_ogm_repos():
    """
    Public OGM repo summaries with latest crawl status and harvest counts.
    """
    repos = await ogm_repo.list_public_repo_summaries()
    return create_response({"repos": repos})


@router.get(
    "/ogm/repos/dashboard",
    include_in_schema=False,
    response_class=HTMLResponse,
)
async def ogm_repo_dashboard(request: Request):
    repos = await ogm_repo.list_public_repo_summaries()

    dashboard_repos = []
    total_harvested = 0
    total_available = 0
    repos_with_aardvark = 0
    enabled_repos = 0
    never_harvested = 0

    for repo in repos:
        harvested_count = int(repo.get("harvested_record_count") or 0)
        available_count = int(repo.get("available_record_count") or 0)
        has_aardvark = bool(repo.get("ogm_has_aardvark"))
        enabled = bool(repo.get("ogm_enabled"))
        last_harvest_completed = repo.get("last_crawl_completed_at")

        total_harvested += harvested_count
        total_available += available_count
        repos_with_aardvark += int(has_aardvark)
        enabled_repos += int(enabled)
        never_harvested += int(not bool(last_harvest_completed))

        dashboard_repos.append(
            {
                **repo,
                "display_last_commit_at": _format_timestamp(repo.get("last_commit_at")),
                "display_last_harvest_at": _format_timestamp(last_harvest_completed),
                "display_last_harvest_started_at": _format_timestamp(
                    repo.get("last_crawl_started_at")
                ),
                "harvest_gap_count": max(harvested_count - available_count, 0),
            }
        )

    summary = {
        "repo_count": len(dashboard_repos),
        "enabled_repo_count": enabled_repos,
        "repos_with_aardvark_count": repos_with_aardvark,
        "never_harvested_count": never_harvested,
        "harvested_record_count": total_harvested,
        "available_record_count": total_available,
    }

    if templates is None:
        rows = "".join(
            (
                "<tr>"
                f"<td>{repo.get('ogm_repo_name') or ''}</td>"
                f"<td>{repo.get('display_last_commit_at') or '-'}</td>"
                f"<td>{repo.get('display_last_harvest_at') or '-'}</td>"
                f"<td>{'yes' if repo.get('ogm_has_aardvark') else 'no'}</td>"
                f"<td>{repo.get('harvested_record_count') or 0}</td>"
                f"<td>{repo.get('available_record_count') or 0}</td>"
                "</tr>"
            )
            for repo in dashboard_repos
        )
        return HTMLResponse(
            (
                "<!doctype html><html><head>"
                "<title>OpenGeoMetadata Repository Dashboard</title>"
                "</head>"
                "<body><h1>OpenGeoMetadata Repository Dashboard</h1>"
                "<p>Templates are unavailable, showing a minimal fallback view.</p>"
                "<table><thead><tr>"
                "<th>Repository</th><th>Last commit</th><th>Last harvest</th>"
                "<th>Aardvark</th><th>Harvested</th><th>Available</th>"
                f"</tr></thead><tbody>{rows}</tbody></table></body></html>"
            )
        )

    return templates.TemplateResponse(
        "ogm_repo_dashboard.html",
        {
            "request": request,
            "title": "OpenGeoMetadata Repository Dashboard",
            "summary": summary,
            "repos": dashboard_repos,
            "generated_at": _format_timestamp(datetime.utcnow()),
        },
    )


@router.get("/ogm/harvest/failures")
async def list_public_ogm_harvest_failures(
    repo_name: Optional[str] = Query(None, description="Filter by a single ogm_repo_name"),
    include_with_errors: bool = Query(
        True,
        description=(
            "Include runs that completed with non-zero import errors (not only ogm_status=failed)"
        ),
    ),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """
    Public OGM harvest failure runs, optionally filtered to a single repo.
    """
    if not include_with_errors:
        failures = await ogm_repo.list_harvest_runs(
            ogm_repo_name=repo_name,
            ogm_status="failed",
            limit=limit,
            offset=offset,
        )
    else:
        # Pull a bounded recent window, then filter runs that are failed OR have import errors.
        window = await ogm_repo.list_harvest_runs(
            ogm_repo_name=repo_name,
            ogm_status=None,
            limit=min(500, limit + offset + 200),
            offset=0,
        )
        filtered = []
        for run in window:
            stats = run.get("ogm_stats_json") or {}
            import_errors = int(stats.get("errors") or 0)
            status = (run.get("ogm_status") or "").lower()
            if status == "failed" or import_errors > 0:
                filtered.append(run)
        failures = filtered[offset : offset + limit]

    for run in failures:
        stats = run.get("ogm_stats_json") or {}
        run["import_error_count"] = int(stats.get("errors") or 0)
        run["imported_count"] = int(stats.get("imported") or 0)
        run["error_samples"] = list(stats.get("error_samples") or [])[:10]
        run["error_signatures"] = list(stats.get("error_signatures") or [])[:10]
        run["failure_reason"] = run.get("ogm_error") or (
            "One or more records failed during import" if run["import_error_count"] > 0 else None
        )

    return create_response(
        {
            "failures": failures,
            "repo_name": repo_name,
            "include_with_errors": include_with_errors,
        }
    )
