from typing import Optional

from fastapi import APIRouter, Query

from app.api.errors import PUBLIC_ERROR_RESPONSES
from app.api.schemas import OGMHarvestFailuresResponse, OGMRepoSummariesResponse
from app.api.v1.utils import create_response
from app.services.ogm_harvest.repository import OGMHarvestRepository

router = APIRouter()
ogm_repo = OGMHarvestRepository()


@router.get("/ogm/repos", response_model=OGMRepoSummariesResponse, responses=PUBLIC_ERROR_RESPONSES)
async def list_public_ogm_repos():
    """
    Public OGM repo summaries with latest crawl status and harvest counts.
    """
    repos = await ogm_repo.list_public_repo_summaries()
    return create_response({"repos": repos})


@router.get(
    "/ogm/harvest/failures",
    response_model=OGMHarvestFailuresResponse,
    responses=PUBLIC_ERROR_RESPONSES,
)
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
