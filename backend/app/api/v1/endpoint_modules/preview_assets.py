"""Access-checked HTTP Range delivery for local and private object storage."""

import re
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, Response, StreamingResponse
from starlette.concurrency import run_in_threadpool

from app.api.errors import COMMON_ERROR_RESPONSES
from app.services.preview_assets.repository import published_for
from app.services.preview_assets.storage import MIME, LocalStorage, check_key, storage
from db.session import async_session

router = APIRouter(responses=COMMON_ERROR_RESPONSES)
HEADERS = {
    "Accept-Ranges": "bytes",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Expose-Headers": "Content-Range, Content-Length, Accept-Ranges, ETag",
    "Cache-Control": "private, no-cache",
}


def allowed_asset(manifest, key):
    return manifest and (
        key == manifest.get("coverage_key")
        or (
            manifest.get("status") == "ready"
            and (
                key == manifest.get("thumbnail_key")
                or any(layer.get("asset_key") == key for layer in manifest.get("layers", []))
            )
        )
    )


@router.options("/resources/{id}/preview-assets/{key}")
async def asset_options(id: str, key: str):
    return Response(
        status_code=204,
        headers={
            **HEADERS,
            "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
            "Access-Control-Allow-Headers": "Range, If-Range, If-None-Match",
        },
    )


@router.api_route(
    "/resources/{id}/preview-assets/{key}", methods=["GET", "HEAD"], response_class=Response
)
async def preview_asset(id: str, key: str, request: Request):
    try:
        check_key(key)
    except ValueError as exc:
        raise HTTPException(404, "Preview asset not found") from exc
    async with async_session() as session:
        manifest = await published_for(id, session)
    if not allowed_asset(manifest, key):
        raise HTTPException(404, "Preview asset not found")
    store = storage()
    if isinstance(store, LocalStorage):
        path = store.path(key)
        if not path.is_file():
            raise HTTPException(404, "Preview asset unavailable")
        return FileResponse(path, media_type=MIME[path.suffix], headers=HEADERS)
    byte_range = request.headers.get("range")
    if byte_range and not re.fullmatch(r"bytes=(\d+-\d*|-\d+)", byte_range):
        raise HTTPException(416, "Unsupported byte range")
    from botocore.exceptions import ClientError

    try:
        if request.method == "HEAD" or request.headers.get("if-range"):
            item = await run_in_threadpool(store.head, key)
            if request.method == "HEAD":
                return Response(
                    headers={
                        **HEADERS,
                        "Content-Length": str(item["ContentLength"]),
                        "ETag": item["ETag"],
                    },
                    media_type=MIME[Path(key).suffix],
                )
            # A mismatched/unsupported validator requires the entire response.
            if request.headers["if-range"] != item["ETag"]:
                byte_range = None
        item = await run_in_threadpool(store.get, key, byte_range)
    except ClientError as exc:
        code = exc.response["Error"]["Code"]
        if code in {"NoSuchKey", "NotFound", "404"}:
            raise HTTPException(404, "Preview asset unavailable") from exc
        if code == "InvalidRange":
            raise HTTPException(416, "Unsatisfiable byte range") from exc
        raise

    def chunks():
        try:
            yield from item["Body"].iter_chunks(256 * 1024)
        finally:
            item["Body"].close()

    headers = {**HEADERS, "Content-Length": str(item["ContentLength"]), "ETag": item["ETag"]}
    if item.get("ContentRange"):
        headers["Content-Range"] = item["ContentRange"]
    return StreamingResponse(
        chunks(),
        status_code=206 if item.get("ContentRange") else 200,
        headers=headers,
        media_type=MIME[Path(key).suffix],
    )
