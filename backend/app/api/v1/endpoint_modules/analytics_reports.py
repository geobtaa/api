"""Public artifacts only; raw archives and health details are never exposed here."""

import csv
import io
import json
import os
import re
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy import text

from app.api.errors import COMMON_ERROR_RESPONSES
from app.services.analytics_reporting.storage import checksum
from db.migrations.analytics_storage import analytics_storage_engine


class ReportingManifest(BaseModel):
    schemaVersion: int
    revision: str
    throughExclusive: str
    latest: str | None
    periods: list[dict[str, Any]]
    stale: bool


class ReportingArtifact(BaseModel):
    model_config = ConfigDict(extra="allow")
    schemaVersion: int
    calculationVersion: str
    privacyVersion: str
    revision: str
    period: str
    start: str
    endExclusive: str
    complete: bool
    missingMonths: list[str]
    sources: dict[str, str]
    totals: dict[str, int | float | None]


router = APIRouter(prefix="/analytics/reports", responses=COMMON_ERROR_RESPONSES)
TABLES = {
    "collections",
    "discoveryViews",
    "comparison",
    "memberResources",
    "memberDaily",
    "queries",
    "zeroQueries",
    "resources",
    "members",
    "clients",
    "endpoints",
    "daily",
    "facets",
}


def enabled():
    if os.getenv("ANALYTICS_REPORTS_PUBLIC", "false").lower() != "true":
        raise HTTPException(503, "Runtime reporting is in shadow validation")


def read_document(period=None, revision=None):
    enabled()
    engine = analytics_storage_engine()
    try:
        with engine.connect() as conn:
            if period is None:
                result = conn.execute(
                    text("SELECT document FROM analytics_reporting_manifest")
                ).scalar()
            else:
                if not re.fullmatch(r"(?:\d{4}-\d{2}|ay-\d{4}|all)", period) or not re.fullmatch(
                    r"[a-f0-9]{64}", revision
                ):
                    raise HTTPException(404, "Report revision unavailable")
                result = conn.execute(
                    text("""SELECT document FROM analytics_reporting_publications
                    WHERE period=:period AND revision=:revision"""),
                    {"period": period, "revision": revision},
                ).scalar()
            if result is None:
                raise HTTPException(404, "Report unavailable")
            return result
    finally:
        engine.dispose()


@router.get("/manifest", response_model=ReportingManifest)
def manifest():
    document = dict(read_document())
    document["stale"] = document["throughExclusive"] < str(
        datetime.now(timezone.utc).date().replace(day=1)
    )
    return JSONResponse(
        document, headers={"Cache-Control": "no-cache", "ETag": f'"{checksum(document)}"'}
    )


@router.get("/{period}/{revision}", response_model=ReportingArtifact)
def report(period: str, revision: str):
    return JSONResponse(
        read_document(period, revision),
        headers={"Cache-Control": "public, max-age=31536000, immutable", "ETag": f'"{revision}"'},
    )


def csv_cell(value):
    value = (
        json.dumps(value, sort_keys=True)
        if isinstance(value, (dict, list))
        else str(value if value is not None else "")
    )
    # Spreadsheet applications must not execute user-entered search text.
    return "'" + value if value.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")) else value


@router.get("/{period}/{revision}/download/{table}", response_model=list[dict[str, Any]])
def download(period: str, revision: str, table: str, format: str = "csv"):
    if table not in TABLES or format not in ("csv", "json"):
        raise HTTPException(404, "Download unavailable")
    rows = read_document(period, revision)[table]
    if format == "json":
        body, media = json.dumps(rows), "application/json"
    else:
        stream = io.StringIO(newline="")
        fields = sorted({k for row in rows for k in row})
        writer = csv.writer(stream)
        writer.writerow(fields)
        writer.writerows([[csv_cell(row.get(k)) for k in fields] for row in rows])
        body, media = stream.getvalue(), "text/csv"
    return Response(
        body,
        media_type=media,
        headers={
            "Content-Disposition": f'attachment; filename="analytics-{period}-{table}.{format}"',
            "Cache-Control": "public, max-age=31536000, immutable",
        },
    )
