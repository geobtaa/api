"""Serve an isolated audit locally for the frontend prepared-preview acceptance page."""

import argparse
import json
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from app.services.preview_assets.storage import MIME, check_key


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--port", type=int, default=8878)
    args = parser.parse_args()
    root = args.directory.resolve()
    app = FastAPI()

    @app.get("/report")
    def report():
        return json.loads((root / "report.json").read_text())

    @app.api_route("/asset/{key}", methods=["GET", "HEAD"])
    def asset(key: str):
        try:
            check_key(key)
        except ValueError as exc:
            raise HTTPException(404, "Unknown audit asset") from exc
        path = root / "assets" / key
        if not path.is_file():
            raise HTTPException(404, "Missing audit asset")
        return FileResponse(path, media_type=MIME[path.suffix])

    uvicorn.run(app, host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
