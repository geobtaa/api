import hmac
import json
import logging
import os
from hashlib import sha256
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request

from app.services.ogm_harvest.repository import OGMHarvestRepository
from app.tasks.ogm_harvest import ogm_harvest_repo

logger = logging.getLogger(__name__)

router = APIRouter()


def _verify_github_signature(body: bytes, signature_header: Optional[str], secret: str) -> bool:
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    their_sig = signature_header.split("=", 1)[1].strip()
    mac = hmac.new(secret.encode("utf-8"), msg=body, digestmod=sha256)
    our_sig = mac.hexdigest()
    return hmac.compare_digest(our_sig, their_sig)


@router.post("/ogm/webhook")
async def ogm_webhook(request: Request):
    """
    GitHub webhook receiver for OpenGeoMetadata push events.

    Security: verifies X-Hub-Signature-256 using OGM_WEBHOOK_SECRET.
    """
    secret = os.getenv("OGM_WEBHOOK_SECRET")
    if not secret:
        raise HTTPException(status_code=500, detail="OGM_WEBHOOK_SECRET is not configured")

    body = await request.body()
    sig = request.headers.get("X-Hub-Signature-256")
    if not _verify_github_signature(body=body, signature_header=sig, secret=secret):
        raise HTTPException(status_code=401, detail="Invalid signature")

    event = request.headers.get("X-GitHub-Event", "")
    if event not in {"push", "ping"}:
        return {"ok": True, "ignored": True, "reason": f"event={event}"}

    if event == "ping":
        return {"ok": True}

    try:
        payload: Dict[str, Any] = json.loads(body.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload") from None

    repo_full = (payload.get("repository") or {}).get("full_name")  # e.g. OpenGeoMetadata/edu.stanford.purl
    if not isinstance(repo_full, str) or "/" not in repo_full:
        raise HTTPException(status_code=400, detail="Missing repository.full_name")

    org, repo_name = repo_full.split("/", 1)
    if org.lower() != "opengeometadata":
        return {"ok": True, "ignored": True, "reason": "not_opengeometadata_org"}

    # Only trigger for repos we explicitly watch in webhook mode
    repo = OGMHarvestRepository()
    row = await repo.get_repo(repo_name)
    if not row or not row.get("ogm_enabled", True):
        return {"ok": True, "ignored": True, "reason": "repo_not_enabled"}

    watch_mode = str(row.get("ogm_watch_mode") or "").lower()
    if watch_mode not in {"webhook", "both"}:
        return {"ok": True, "ignored": True, "reason": f"watch_mode={watch_mode}"}

    task = ogm_harvest_repo.delay(repo_name=repo_name, trigger="webhook")
    return {"ok": True, "queued": repo_name, "task_id": task.id}

