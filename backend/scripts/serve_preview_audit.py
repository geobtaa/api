"""Serve an isolated audit locally for the frontend prepared-preview acceptance page."""

import argparse
import json
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse

from app.services.preview_assets.storage import MIME, check_key


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--port", type=int, default=8878)
    parser.add_argument(
        "--supplemental", type=Path, help="Separate supplemental evidence directory"
    )
    parser.add_argument(
        "--records", type=Path, help="Original record snapshots for browser acceptance"
    )
    args = parser.parse_args()
    root = args.directory.resolve()
    roots = [root] + ([args.supplemental.resolve()] if args.supplemental else [])
    entries = json.loads(args.records.read_text()) if args.records else []
    records = {item.get("record", item)["id"]: item.get("record", item) for item in entries}
    app = FastAPI()

    @app.middleware("http")
    async def evidence(request: Request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/asset/"):
            with (root / "browser-requests.jsonl").open("a") as output:
                output.write(
                    json.dumps(
                        {
                            "path": request.url.path,
                            "range": request.headers.get("range"),
                            "status": response.status_code,
                            "length": response.headers.get("content-length"),
                            "content_range": response.headers.get("content-range"),
                        }
                    )
                    + "\n"
                )
        return response

    @app.get("/report")
    def report():
        return [
            {**row, "record": records.get(row["id"], row.get("record"))}
            for directory in roots
            for row in json.loads((directory / "report.json").read_text())
        ]

    @app.api_route("/asset/{key}", methods=["GET", "HEAD"])
    def asset(key: str):
        try:
            check_key(key)
        except ValueError as exc:
            raise HTTPException(404, "Unknown audit asset") from exc
        path = next(
            (
                directory / "assets" / key
                for directory in roots
                if (directory / "assets" / key).is_file()
            ),
            None,
        )
        if path is None:
            raise HTTPException(404, "Missing audit asset")
        return FileResponse(path, media_type=MIME[path.suffix])

    uvicorn.run(app, host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
