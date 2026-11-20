"""One-way, resumable Kithe feed into the candidate's protected ingestion command."""

import fcntl
import hashlib
import json
import os
import tempfile
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit
from uuid import NAMESPACE_URL, uuid5

import requests

from app.services.bridge_sync.client import KitheBridgeClient


def persist(path, data):
    with tempfile.NamedTemporaryFile(dir=path.parent, mode="w", delete=False) as temp:
        json.dump(data, temp)
        temp.flush()
        os.fsync(temp.fileno())
    os.replace(temp.name, path)
    descriptor = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def sync_candidate(client, target, credential, directory, *, candidate_id, budget=3000):
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    checkpoint = directory / "checkpoint.json"
    source = client.base_url
    with (directory / "run.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {"status": "busy"}
        state = (
            json.loads(checkpoint.read_text())
            if checkpoint.exists()
            else {
                "candidate_id": candidate_id,
                "source": source,
                "target": target,
                "watermark": None,
                "cursor": None,
                "cutoff": None,
                "counts": {},
            }
        )
        if (state.get("candidate_id"), state["source"], state["target"]) != (
            candidate_id,
            source,
            target,
        ):
            raise ValueError("Checkpoint belongs to a different candidate or source")
        if state["cutoff"] is None:
            state.update(
                cutoff=(datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat(), counts={}
            )
            persist(checkpoint, state)
        stop = time.monotonic() + budget
        pending = directory / "page.json"
        while time.monotonic() < stop:
            if pending.exists():
                saved = json.loads(pending.read_text())
                if (saved["cutoff"], saved["cursor"]) != (state["cutoff"], state["cursor"]):
                    pending.unlink()
                    continue
            else:
                page = client.fetch_page(
                    cursor=state["cursor"], limit=100, changed_since=state["watermark"]
                )
                if page.has_more and (not page.data or page.next_cursor == state["cursor"]):
                    raise ValueError("Bridge cursor did not advance")
                saved = {
                    "records": page.data,
                    "has_more": page.has_more,
                    "next": page.next_cursor,
                    "cutoff": state["cutoff"],
                    "cursor": state["cursor"],
                }
                persist(pending, saved)
            if saved["records"]:
                payload = {"records": saved["records"]}
                digest = hashlib.sha256(json.dumps(saved, sort_keys=True).encode()).hexdigest()
                key = str(uuid5(NAMESPACE_URL, f"{candidate_id}:{source}:{target}:{digest}"))
                response = requests.post(
                    target,
                    json=payload,
                    timeout=120,
                    allow_redirects=False,
                    headers={
                        "X-GEOMG-Bridge-Token": credential,
                        "Idempotency-Key": key,
                        "X-GEOMG-Request": "1",
                    },
                )
                if response.status_code != 200:
                    raise RuntimeError(f"Candidate ingestion returned HTTP {response.status_code}")
                result = response.json()
                if result["batch_id"] != key or [r.get("id") for r in saved["records"]] != [
                    r["resource_id"] for r in result["items"]
                ]:
                    raise RuntimeError("Ingestion outcomes do not reconcile")
                counts = Counter(state["counts"])
                counts.update(r["outcome"] for r in result["items"])
                state["counts"] = dict(counts)
            state["cursor"] = saved["next"] if saved["has_more"] else None
            if not saved["has_more"]:
                state.update(watermark=state["cutoff"], cutoff=None)
            persist(checkpoint, state)
            pending.unlink()
            if not saved["has_more"]:
                return {
                    "status": "complete",
                    "watermark": state["watermark"],
                    "counts": state["counts"],
                }
        return {"status": "paused", "counts": state["counts"]}


def run():
    if os.getenv("KAMAL_DEST") != "dev2":
        raise RuntimeError("Candidate Bridge requires dev2")
    client = KitheBridgeClient()
    origin = urlsplit(client.base_url)
    if origin.scheme != "https" or origin.hostname != "geomg.lib.umn.edu" or not client.verify_ssl:
        raise ValueError("Candidate requires the verified production Kithe Bridge")
    return sync_candidate(
        client,
        os.environ["GEOMG_INGEST_URL"],
        os.environ["GEOMG_INGEST_TOKEN"],
        Path(os.environ["GEOMG_BRIDGE_STATE_DIR"]),
        candidate_id=os.environ["GEOMG_CANDIDATE_ID"],
    )
