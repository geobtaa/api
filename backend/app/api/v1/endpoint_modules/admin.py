import html as _html
import ipaddress
import logging
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.security import HTTPBasic
from pydantic import BaseModel

from app.api.v1.auth import verify_credentials
from app.api.v1.utils import create_response, sanitize_for_json
from app.services.admin_service import (
    AdminService,
    CacheManagementError,
    CacheManagementService,
    ReindexingError,
    ReindexingService,
    ResourceNotFoundError,
    ResourceProcessingError,
    ResourceProcessingService,
)
from app.services.api_key_service import APIKeyService
from app.services.bridge_sync.repository import BridgeSyncRepository
from app.services.cache_service import CacheService
from app.services.gin_blog_service import GINBlogService
from app.services.ogm_harvest.repository import OGMHarvestRepository
from app.tasks.bridge_sync import bridge_sync_all
from app.tasks.gin_blog_sync import gin_blog_sync
from app.tasks.ogm_harvest import ogm_harvest_all, ogm_harvest_repo

logger = logging.getLogger(__name__)

security = HTTPBasic()
router = APIRouter(dependencies=[Depends(verify_credentials)])


def validate_ip_addresses(ip_list: List[str]) -> None:
    """Validate a list of IP addresses.

    Raises HTTPException if any IP address is invalid.
    Supports both IPv4 and IPv6 addresses.
    """
    for ip_str in ip_list:
        try:
            ipaddress.ip_address(ip_str)
        except ValueError as err:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid IP address: {ip_str}. Must be a valid IPv4 or IPv6 address.",
            ) from err


def get_admin_service() -> AdminService:
    """Dependency injection for AdminService."""
    cache_management_service = CacheManagementService()
    reindexing_service = ReindexingService()
    resource_processing_service = ResourceProcessingService()
    return AdminService(cache_management_service, reindexing_service, resource_processing_service)


# Module-level singleton for dependency injection
_admin_service_dependency = Depends(get_admin_service)

# API Key Service instance (handles its own async engine and session)
api_key_service = APIKeyService()
ogm_repo = OGMHarvestRepository()
bridge_repo = BridgeSyncRepository()


# Pydantic models for request/response
class CreateAPIKeyRequest(BaseModel):
    tier_name: str
    name: Optional[str] = None
    allowed_ips: Optional[List[str]] = None


class UpdateAPIKeyRequest(BaseModel):
    tier_name: Optional[str] = None
    is_active: Optional[bool] = None
    name: Optional[str] = None
    allowed_ips: Optional[List[str]] = None


class UpdateOGMRepoRequest(BaseModel):
    ogm_enabled: Optional[bool] = None
    ogm_watch_mode: Optional[str] = None  # weekly|webhook|both|manual
    ogm_notes: Optional[str] = None
    ogm_tags: Optional[dict] = None


class TriggerOGMHarvestRequest(BaseModel):
    ogm_repo_name: Optional[str] = None
    ogm_all: bool = False
    ogm_trigger: str = "manual"


class TriggerBridgeSyncRequest(BaseModel):
    bridge_trigger: str = "manual"
    limit: Optional[int] = None


class TriggerGINBlogSyncRequest(BaseModel):
    run_now: bool = False


@router.post("/cache/clear")
async def clear_cache(
    cache_type: Optional[str] = Query(
        None, description="Type of cache to clear (search, item, suggest, all)"
    ),
    service: AdminService = _admin_service_dependency,
):
    """Clear specified cache or all cache if not specified."""
    try:
        result = await service.clear_cache(cache_type)
        return create_response(result)
    except CacheManagementError as e:
        logger.error(f"Cache management error: {str(e)}")
        return create_response({"error": str(e)}, status_code=500)
    except Exception as e:
        logger.error(f"Unexpected error clearing cache: {str(e)}")
        return create_response({"error": f"Failed to clear cache: {str(e)}"}, status_code=500)


class CachePurgeRequest(BaseModel):
    tags: Optional[List[str]] = None
    prefix: Optional[str] = None
    flush_all: bool = False


@router.post("/cache/purge")
async def purge_cache(
    body: CachePurgeRequest,
):
    """Aggressive cache purge.

    - tags: invalidates by tag (recommended)
    - prefix: invalidates by key prefix (fallback)
    - flush_all: nukes Redis DB (emergency)
    """
    cache = CacheService()
    try:
        if body.flush_all:
            ok = await cache.flush_all()
            return create_response({"ok": bool(ok), "mode": "flush_all"})

        if body.tags:
            deleted = await cache.invalidate_tags(body.tags)
            return create_response(
                {"ok": True, "mode": "tags", "deleted": deleted, "tags": body.tags}
            )

        if body.prefix:
            from app.services.cache_service import invalidate_cache_with_prefix

            ok = await invalidate_cache_with_prefix(body.prefix)
            return create_response({"ok": bool(ok), "mode": "prefix", "prefix": body.prefix})

        raise HTTPException(status_code=400, detail="Provide tags, prefix, or flush_all")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error purging cache: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/reindex")
async def reindex(
    callback: Optional[str] = Query(None, description="JSONP callback name"),
    service: AdminService = _admin_service_dependency,
):
    """Trigger reindexing of all items in Elasticsearch."""
    try:
        result = await service.reindex_resources()
        return create_response(result, callback)
    except ReindexingError as e:
        logger.error(f"Reindexing error: {str(e)}")
        raise HTTPException(
            status_code=500, detail={"message": "Reindexing failed", "error": str(e)}
        ) from e
    except Exception as e:
        logger.error(f"Unexpected error during reindexing: {str(e)}")
        raise HTTPException(
            status_code=500, detail={"message": "Reindexing failed", "error": str(e)}
        ) from e


@router.post("/resources/{id}/summarize")
async def summarize_resource(
    id: str,
    background_tasks: BackgroundTasks,
    callback: Optional[str] = Query(None, description="JSONP callback name"),
    service: AdminService = _admin_service_dependency,
):
    """
    Trigger the generation of a summary for a resource.
    This endpoint will:
    1. Fetch the resource metadata
    2. Get the asset path and type
    3. Trigger an asynchronous task to generate the summary
    4. Return immediately with task ID
    """
    try:
        result = await service.summarize_resource(id)

        # Sanitize the response data before returning
        sanitized_response = sanitize_for_json(result)
        return create_response(sanitized_response, callback)
    except ResourceNotFoundError as e:
        logger.error(f"Resource not found: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ResourceProcessingError as e:
        logger.error(f"Resource processing error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Unexpected error triggering summary generation for resource {id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/resources/{id}/identify-geo-entities")
async def identify_geo_entities(
    id: str,
    background_tasks: BackgroundTasks,
    callback: Optional[str] = Query(None, description="JSONP callback name"),
    service: AdminService = _admin_service_dependency,
):
    """
    Trigger the identification of geographic entities in a resource.
    This endpoint will:
    1. Fetch the resource metadata
    2. Trigger an asynchronous task to identify geographic entities
    3. Return immediately with task ID
    """
    try:
        result = await service.identify_geo_entities(id)
        return create_response(result, callback)
    except ResourceNotFoundError as e:
        logger.error(f"Resource not found: {str(e)}")
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ResourceProcessingError as e:
        logger.error(f"Resource processing error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) from e
    except Exception as e:
        logger.error(
            f"Unexpected error triggering geographic entity identification "
            f"for resource {id}: {str(e)}"
        )
        raise HTTPException(status_code=500, detail=str(e)) from e


# API Key Management Endpoints


@router.post("/api-keys")
async def create_api_key(
    request: CreateAPIKeyRequest,
):
    """Create a new API key."""
    try:
        # Validate IP addresses if provided
        if request.allowed_ips:
            validate_ip_addresses(request.allowed_ips)

        result = await api_key_service.create_api_key(
            tier_name=request.tier_name,
            name=request.name,
            allowed_ips=request.allowed_ips,
        )

        if result is None:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to create API key. Tier '{request.tier_name}' may not exist.",
            )

        return create_response(result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating API key: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/api-keys")
async def list_api_keys():
    """List all API keys."""
    try:
        keys = await api_key_service.list_api_keys()
        return create_response({"keys": keys})
    except Exception as e:
        logger.error(f"Error listing API keys: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.patch("/api-keys/{key_id}")
async def update_api_key(
    key_id: int,
    request: UpdateAPIKeyRequest,
):
    """Update an API key.

    Note: To remove IP restrictions, pass allowed_ips as an empty list [].
    To keep IP restrictions unchanged, omit the allowed_ips field.
    """
    try:
        # Validate IP addresses if provided
        if request.allowed_ips is not None:
            # Empty list means remove restriction (will be handled by service)
            if request.allowed_ips:
                validate_ip_addresses(request.allowed_ips)

        allowed_ips_update = request.allowed_ips

        updated = await api_key_service.update_api_key_by_id(
            key_id=key_id,
            tier_name=request.tier_name,
            is_active=request.is_active,
            name=request.name,
            allowed_ips=allowed_ips_update,
        )

        if not updated:
            # Could be missing key, missing tier, or no fields to update
            raise HTTPException(status_code=400, detail="Failed to update API key")

        return create_response({"message": "API key updated successfully"})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating API key: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/api-keys/{key_id}")
async def revoke_api_key(key_id: int):
    """Revoke (deactivate) an API key."""
    try:
        # Use service method that handles its own async session (NullPool) to
        # avoid cross-event-loop issues with the shared database connection.
        success = await api_key_service.revoke_api_key_by_id(key_id)

        if not success:
            raise HTTPException(status_code=500, detail="Failed to revoke API key")

        return create_response({"message": "API key revoked successfully"})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error revoking API key: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/api-tiers")
async def list_api_tiers():
    """List all service tiers."""
    try:
        tiers = await api_key_service.list_tiers()
        return create_response({"tiers": tiers})
    except Exception as e:
        logger.error(f"Error listing API tiers: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) from e


# --- OpenGeoMetadata (OGM) admin endpoints ---


@router.get("/ogm/repos")
async def list_ogm_repos():
    """List configured OGM repos (watch list)."""
    repos = await ogm_repo.list_repos()
    return create_response({"repos": repos})


@router.patch("/ogm/repos/{repo_name}")
async def update_ogm_repo(repo_name: str, body: UpdateOGMRepoRequest):
    """Create or update a repo watch entry."""
    if body.ogm_watch_mode is not None:
        mode = body.ogm_watch_mode.lower().strip()
        if mode not in {"weekly", "webhook", "both", "manual"}:
            raise HTTPException(status_code=400, detail="Invalid ogm_watch_mode")
    await ogm_repo.upsert_repo(
        ogm_repo_name=repo_name,
        ogm_enabled=body.ogm_enabled if body.ogm_enabled is not None else True,
        ogm_watch_mode=body.ogm_watch_mode or "weekly",
        ogm_notes=body.ogm_notes,
        ogm_tags=body.ogm_tags,
    )
    saved = await ogm_repo.get_repo(repo_name)
    return create_response({"repo": saved})


@router.post("/ogm/harvest")
async def trigger_ogm_harvest(body: TriggerOGMHarvestRequest):
    """Trigger a harvest for a single repo or all repos (enqueues Celery)."""
    if body.ogm_all:
        task = ogm_harvest_all.delay(trigger=body.ogm_trigger)
        return create_response({"queued": "all", "task_id": task.id})

    if not body.ogm_repo_name:
        raise HTTPException(status_code=400, detail="Provide ogm_repo_name or set ogm_all=true")

    task = ogm_harvest_repo.delay(repo_name=body.ogm_repo_name, trigger=body.ogm_trigger)
    return create_response({"queued": body.ogm_repo_name, "task_id": task.id})


@router.post("/bridge/sync")
async def trigger_bridge_sync(body: TriggerBridgeSyncRequest):
    """Trigger a bridge sync crawl (enqueues Celery)."""
    task = bridge_sync_all.delay(trigger=body.bridge_trigger, limit=body.limit)
    return create_response(
        {
            "queued": "kithe_bridge",
            "task_id": task.id,
            "bridge_trigger": body.bridge_trigger,
            "limit": body.limit,
        }
    )


BRIDGE_SYNC_TASK_NAME = "bridge_sync_all"


@router.post("/bridge/sync/cancel")
async def cancel_bridge_sync():
    """Cancel all running bridge sync runs and revoke active/reserved
    bridge_sync_all Celery tasks."""
    import asyncio

    runs_cancelled = await bridge_repo.cancel_all_running_runs(
        reason="cancelled via admin (POST /bridge/sync/cancel)"
    )

    task_ids_revoked: List[str] = []
    try:
        from app.tasks.worker import celery_app

        def _collect_and_revoke():
            def task_ids_for_name(task_map: dict, name: str) -> List[str]:
                ids = []
                for _worker, tasks in task_map.items():
                    for t in tasks or []:
                        if t.get("name") == name and t.get("id"):
                            ids.append(t["id"])
                return ids

            insp = celery_app.control.inspect(timeout=2.0)
            active_map = insp.active() or {}
            reserved_map = insp.reserved() or {}
            active_ids = task_ids_for_name(active_map, BRIDGE_SYNC_TASK_NAME)
            reserved_ids = [
                tid
                for tid in task_ids_for_name(reserved_map, BRIDGE_SYNC_TASK_NAME)
                if tid not in active_ids
            ]
            for tid in active_ids:
                celery_app.control.revoke(tid, terminate=True)
            for tid in reserved_ids:
                celery_app.control.revoke(tid, terminate=False)
            return active_ids + reserved_ids

        task_ids_revoked = await asyncio.to_thread(_collect_and_revoke)
    except Exception as e:
        logger.warning("Celery revoke failed (runs still cancelled): %s", e)

    return create_response(
        {
            "runs_cancelled": runs_cancelled,
            "tasks_revoked": task_ids_revoked,
        }
    )


@router.post("/home/blog/sync")
async def trigger_home_blog_sync(body: TriggerGINBlogSyncRequest):
    """Trigger a GIN blog sync (enqueues Celery by default)."""
    if body.run_now:
        service_result = await GINBlogService().sync_posts_from_github()
        return create_response({"queued": "inline", "result": service_result})
    task = gin_blog_sync.delay()
    return create_response({"queued": "gin_blog_sync", "task_id": task.id})


@router.get("/ogm/harvest/runs")
async def list_ogm_harvest_runs(
    repo_name: Optional[str] = Query(None, description="Filter by ogm_repo_name"),
    status: Optional[str] = Query(None, description="Filter by ogm_status"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    runs = await ogm_repo.list_harvest_runs(
        ogm_repo_name=repo_name,
        ogm_status=status,
        limit=limit,
        offset=offset,
    )
    return create_response({"runs": runs})


@router.get("/ogm/harvest/runs/{run_id}")
async def get_ogm_harvest_run(run_id: int):
    run = await ogm_repo.get_harvest_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return create_response({"run": run})


@router.get("/bridge/sync/runs")
async def list_bridge_sync_runs(
    status: Optional[str] = Query(None, description="Filter by bridge_status"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    runs = await bridge_repo.list_sync_runs(bridge_status=status, limit=limit, offset=offset)
    return create_response({"runs": runs})


@router.get("/bridge/sync/runs/{run_id}")
async def get_bridge_sync_run(run_id: int):
    run = await bridge_repo.get_sync_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return create_response({"run": run})


@router.get("/bridge/sync/status")
async def bridge_sync_status(
    include_celery: bool = Query(False, description="Include Celery active tasks (best-effort)"),
    runs_limit: int = Query(200, ge=1, le=1000, description="How many recent runs to summarize"),
):
    payload = await bridge_repo.list_status_counts(runs_limit=runs_limit)

    if include_celery:
        try:
            import asyncio as _asyncio

            from app.tasks.worker import celery_app

            def _inspect_active():
                insp = celery_app.control.inspect(timeout=1.0)
                return insp.active() or {}

            payload["celery_active"] = await _asyncio.to_thread(_inspect_active)
        except Exception:
            payload["celery_active"] = {"error": "celery inspect failed"}

    return create_response(payload)


@router.get("/bridge/missing")
async def list_bridge_missing(
    limit: int = Query(200, ge=1, le=2000),
    offset: int = Query(0, ge=0),
):
    missing = await bridge_repo.list_missing(limit=limit, offset=offset)
    return create_response({"missing": missing})


@router.get("/ogm/harvest/status")
async def ogm_harvest_status(
    include_celery: bool = Query(False, description="Include Celery active tasks (best-effort)"),
    runs_limit: int = Query(200, ge=1, le=1000, description="How many recent runs to summarize"),
    format: str = Query("html", description="Response format: html|json"),
):
    """
    Single-pane-of-glass OGM harvest status.

    This is designed to give you visibility without needing Flower/log tailing.
    """
    runs = await ogm_repo.list_harvest_runs(limit=runs_limit, offset=0)
    repos = await ogm_repo.list_repos()

    counts = {"running": 0, "success": 0, "failed": 0, "other": 0}
    for r in runs:
        s = (r.get("ogm_status") or "").lower()
        if s in counts:
            counts[s] += 1
        else:
            counts["other"] += 1

    running_runs = [r for r in runs if (r.get("ogm_status") or "").lower() == "running"]

    celery_active = None
    if include_celery:
        try:
            import asyncio as _asyncio

            from app.tasks.worker import celery_app

            def _inspect_active():
                insp = celery_app.control.inspect(timeout=1.0)
                return insp.active() or {}

            celery_active = await _asyncio.to_thread(_inspect_active)
        except Exception:
            celery_active = {"error": "celery inspect failed"}

    payload = {
        "counts_last_runs": counts,
        "running_runs": running_runs,
        "repos": repos,
        "celery_active": celery_active,
    }

    if (format or "").lower() == "json":
        return create_response(payload)

    # --- HTML view (human-friendly) ---
    from datetime import datetime, timezone

    def _parse_dt(s: Optional[str]) -> Optional[datetime]:
        if not s:
            return None
        try:
            # stored as ISO without timezone
            return datetime.fromisoformat(s)
        except Exception:
            return None

    def _age(dt: Optional[datetime]) -> str:
        if not dt:
            return "-"
        delta = datetime.now(timezone.utc).replace(tzinfo=None) - dt
        secs = int(delta.total_seconds())
        if secs < 0:
            return "0s"
        if secs < 60:
            return f"{secs}s"
        mins = secs // 60
        if mins < 60:
            return f"{mins}m"
        hrs = mins // 60
        return f"{hrs}h{mins % 60:02d}m"

    # Index latest run per repo (from provided runs list, already desc by ogm_id)
    latest_by_repo = {}
    for r in runs:
        repo_name = r.get("ogm_repo_name")
        if repo_name and repo_name not in latest_by_repo:
            latest_by_repo[repo_name] = r

    # Sort repos for stable scan
    repos_sorted = sorted(
        repos, key=lambda r: (r.get("ogm_enabled") is not True, r.get("ogm_repo_name") or "")
    )

    rows_html = []
    for repo in repos_sorted:
        name = repo.get("ogm_repo_name") or ""
        enabled = bool(repo.get("ogm_enabled"))
        watch_mode = (repo.get("ogm_watch_mode") or "").lower()

        run = latest_by_repo.get(name) or {}
        run_id = run.get("ogm_id")
        run_status = (run.get("ogm_status") or "").lower() or "-"
        started = _parse_dt(run.get("ogm_started_at"))
        completed = _parse_dt(run.get("ogm_completed_at"))
        stats = run.get("ogm_stats_json") or {}
        stage = stats.get("stage") or "-"
        updated_at = stats.get("updated_at") or None
        # updated_at stored as ISO string with Z; keep as-is for display.
        # Compute age if parseable.
        upd_dt = None
        if isinstance(updated_at, str):
            try:
                s = updated_at.rstrip("Z")
                upd_dt = datetime.fromisoformat(s)
            except Exception:
                upd_dt = None
        imported = stats.get("imported")
        errors = stats.get("errors")

        err = run.get("ogm_error") or ""
        err_short = (err[:160] + "…") if len(err) > 160 else err

        # duration: if running, show age since started; else duration between started/completed
        if started and not completed:
            dur = _age(started)
        elif started and completed:
            dur_secs = int((completed - started).total_seconds())
            dur = f"{dur_secs}s" if dur_secs < 60 else f"{dur_secs // 60}m{dur_secs % 60:02d}s"
        else:
            dur = "-"

        css_class = (
            "ok"
            if run_status == "success"
            else ("bad" if run_status == "failed" else ("run" if run_status == "running" else ""))
        )
        enabled_txt = "yes" if enabled else "no"

        rows_html.append(
            "<tr class='{cls}'>"
            "<td><code>{name}</code></td>"
            "<td>{enabled}</td>"
            "<td><code>{mode}</code></td>"
            "<td><code>{status}</code></td>"
            "<td><code>{stage}</code></td>"
            "<td>{run_id}</td>"
            "<td>{dur}</td>"
            "<td>{upd}</td>"
            "<td>{imp}</td>"
            "<td>{errs}</td>"
            "<td><small>{err}</small></td>"
            "</tr>".format(
                cls=_html.escape(css_class),
                name=_html.escape(name),
                enabled=_html.escape(enabled_txt),
                mode=_html.escape(watch_mode or "-"),
                status=_html.escape(run_status),
                stage=_html.escape(str(stage)),
                run_id=_html.escape(str(run_id) if run_id is not None else "-"),
                dur=_html.escape(dur),
                upd=_html.escape((_age(upd_dt) + " ago") if upd_dt else "-"),
                imp=_html.escape(str(imported) if imported is not None else "-"),
                errs=_html.escape(str(errors) if errors is not None else "-"),
                err=_html.escape(err_short) if err_short else "",
            )
        )

    counts_html = (
        f"<div><strong>Counts (last {runs_limit} runs)</strong>: "
        f"running={counts['running']}, success={counts['success']}, "
        f"failed={counts['failed']}, other={counts['other']}</div>"
    )

    html_body = f"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>OGM Harvest Status</title>
  <style>
    body {{
      font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial;
      margin: 16px;
    }}
    .meta {{ margin-bottom: 12px; color: #333; }}
    .meta code {{ background: #f2f2f2; padding: 2px 6px; border-radius: 4px; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #ddd; padding: 8px; vertical-align: top; }}
    th {{ position: sticky; top: 0; background: #fafafa; text-align: left; }}
    tr.run td {{ background: #fffceb; }}
    tr.ok td {{ background: #f0fff4; }}
    tr.bad td {{ background: #fff5f5; }}
    small {{ color: #444; }}
  </style>
  <meta http-equiv="refresh" content="10" />
</head>
<body>
  <h2>OGM Harvest Status</h2>
  <div class="meta">
    {counts_html}
    <div><strong>Auto-refresh</strong>: every 10 seconds</div>
    <div><strong>JSON</strong>: <code>?format=json</code></div>
  </div>
  <table>
    <thead>
      <tr>
        <th>repo</th>
        <th>enabled</th>
        <th>watch</th>
        <th>run_status</th>
        <th>stage</th>
        <th>run_id</th>
        <th>duration</th>
        <th>last_update</th>
        <th>imported</th>
        <th>errors</th>
        <th>error</th>
      </tr>
    </thead>
    <tbody>
      {"".join(rows_html)}
    </tbody>
  </table>
</body>
</html>
"""
    return HTMLResponse(content=html_body, status_code=200)


@router.get("/ogm/repos/{repo_name}/missing")
async def list_ogm_missing(
    repo_name: str,
    limit: int = Query(200, ge=1, le=2000),
    offset: int = Query(0, ge=0),
):
    missing = await ogm_repo.list_missing_for_repo(repo_name, limit=limit, offset=offset)
    return create_response({"repo": repo_name, "missing": missing})


@router.get("/ogm/harvest/runs/{run_id}/dumps")
async def get_ogm_dump_manifest(run_id: int):
    run = await ogm_repo.get_harvest_run(run_id)
    if not run or not run.get("ogm_dump_dir"):
        raise HTTPException(status_code=404, detail="Dump not found for run")
    dump_dir = Path(run["ogm_dump_dir"])
    manifest_path = dump_dir / "manifest.json"
    if not manifest_path.exists():
        raise HTTPException(status_code=404, detail="manifest.json not found")
    return FileResponse(str(manifest_path), media_type="application/json")


@router.get("/ogm/harvest/runs/{run_id}/dumps/{filename}")
async def download_ogm_dump_file(run_id: int, filename: str):
    run = await ogm_repo.get_harvest_run(run_id)
    if not run or not run.get("ogm_dump_dir"):
        raise HTTPException(status_code=404, detail="Dump not found for run")

    dump_dir = Path(run["ogm_dump_dir"])
    # Prevent path traversal
    candidate = (dump_dir / filename).resolve()
    if dump_dir.resolve() not in candidate.parents and candidate != dump_dir.resolve():
        raise HTTPException(status_code=400, detail="Invalid filename")

    if not candidate.exists() or not candidate.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    # Basic content type mapping
    media_type = "application/octet-stream"
    if filename.endswith(".json") or filename.endswith(".ndjson"):
        media_type = "application/json"
    elif filename.endswith(".parquet"):
        media_type = "application/octet-stream"

    return FileResponse(str(candidate), media_type=media_type, filename=filename)
