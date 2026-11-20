"""Read-only local fixture catalog; never an administrative Resource store."""

import hashlib
import json
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.auth import Actor, require_permissions

ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "geoportal"
router = APIRouter(prefix="/admin/resource-fixtures", tags=["development fixtures"])


class Fixture(BaseModel):
    filename: str
    purpose: str
    metadata: dict[str, Any]


class Catalog(BaseModel):
    source_commit: str
    items: list[Fixture]


def load_catalog(root: Path = ROOT) -> Catalog:
    manifest = json.loads((root / "manifest.json").read_text())
    items = []
    ids = set()
    for entry in manifest["entries"]:
        path = (root / entry["path"]).resolve()
        if not path.is_relative_to(root.resolve()):
            raise ValueError("Fixture path escapes snapshot")
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != entry["sha256"]:
            raise ValueError(f"Fixture checksum mismatch: {entry['path']}")
        record = json.loads(raw)
        if record.get("id") != entry["resource_id"]:
            raise ValueError("Fixture identity mismatch")
        if entry["starter"]:
            identifier = record.get("id")
            if not isinstance(identifier, str) or not identifier or identifier in ids:
                raise ValueError("Starter Resource IDs must be unique nonempty strings")
            if not isinstance(record.get("dct_title_s"), str):
                raise ValueError("Starter title must be a string")
            ids.add(identifier)
            items.append(Fixture(filename=entry["path"], purpose=entry["purpose"], metadata=record))
    return Catalog(source_commit=manifest["source_commit"], items=items)


@router.get(
    "", response_model=Catalog, operation_id="fixtures_catalog", summary="List development fixtures"
)
async def catalog(
    request: Request,
    actor: Annotated[Actor, Depends(require_permissions("admin.session:read"))],
):
    """Preview bundled starter fixtures in development/test; no writes or remote requests."""
    if request.app.state.settings.app_env not in {"development", "test"}:
        raise HTTPException(404, "Fixture catalog is available only in development")
    try:
        return load_catalog()
    except (OSError, ValueError, KeyError) as exc:
        raise HTTPException(503, "Fixture snapshot unavailable or invalid") from exc


if __name__ == "__main__":
    result = load_catalog()
    print(f"Verified Geoportal snapshot; {len(result.items)} unique starter Resources")
