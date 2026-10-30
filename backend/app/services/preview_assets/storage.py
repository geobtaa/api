"""Immutable derivative bytes. Public URLs are access-checked API routes."""

import hashlib
import os
import re
import shutil
import tempfile
from pathlib import Path
from urllib.parse import quote

from .models import Outcome, PreviewError

KEY = re.compile(r"^[a-f0-9]{64}\.(tif|pmtiles|png)$")
MIME = {".tif": "image/tiff", ".pmtiles": "application/vnd.pmtiles", ".png": "image/png"}


def asset_url(resource_id: str, key: str) -> str:
    base = os.getenv("APPLICATION_URL", "http://localhost:8000").rstrip("/")
    if not base.endswith("/api/v1"):
        base += "/api/v1"
    return f"{base}/resources/{quote(resource_id, safe='')}/preview-assets/{key}"


def check_key(key):
    if not KEY.fullmatch(key):
        raise ValueError("Invalid preview asset key")


def file_key(path: Path):
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    key = digest + path.suffix
    check_key(key)
    return key


class LocalStorage:
    def __init__(self, root: Path):
        self.root = root

    def put(self, path: Path) -> str:
        key = file_key(path)
        self.root.mkdir(parents=True, exist_ok=True)
        if not (self.root / key).exists():
            fd, name = tempfile.mkstemp(dir=self.root)
            try:
                with os.fdopen(fd, "wb") as target, path.open("rb") as source:
                    shutil.copyfileobj(source, target)
                os.replace(name, self.root / key)
            finally:
                Path(name).unlink(missing_ok=True)
        return key

    def path(self, key: str):
        check_key(key)
        return self.root / key


class S3Storage:
    def __init__(self, bucket: str, prefix="previews/", client=None):
        if client is None:
            import boto3
            from botocore.config import Config

            client = boto3.client(
                "s3",
                endpoint_url=os.getenv("PREVIEW_S3_ENDPOINT"),
                config=Config(
                    connect_timeout=10,
                    read_timeout=30,
                    retries={"total_max_attempts": 3, "mode": "standard"},
                ),
            )
        self.client, self.bucket, self.prefix = client, bucket, prefix

    def put(self, path: Path) -> str:
        from boto3.s3.transfer import TransferConfig

        key = file_key(path)
        self.client.upload_file(
            str(path),
            self.bucket,
            self.prefix + key,
            ExtraArgs={"ContentType": MIME[path.suffix]},
            Config=TransferConfig(max_concurrency=2),
        )
        return key

    def get(self, key: str, byte_range: str | None = None):
        check_key(key)
        params = {"Bucket": self.bucket, "Key": self.prefix + key}
        if byte_range:
            params["Range"] = byte_range
        return self.client.get_object(**params)

    def head(self, key: str):
        check_key(key)
        return self.client.head_object(Bucket=self.bucket, Key=self.prefix + key)


def storage():
    if os.getenv("PREVIEW_STORAGE", "local") == "local":
        return LocalStorage(Path(os.getenv("PREVIEW_ASSET_ROOT", "data/preview-assets")))
    if os.getenv("PREVIEW_STORAGE") == "s3" and os.getenv("PREVIEW_S3_BUCKET"):
        return S3Storage(os.environ["PREVIEW_S3_BUCKET"])
    raise PreviewError(Outcome.INVALID, "Preview storage is not configured")
