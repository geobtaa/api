"""Bounded source retrieval and extraction, independent of web request handlers."""

import hashlib
import ipaddress
import socket
import ssl
import stat
import time
import zipfile
from contextlib import ExitStack, nullcontext
from pathlib import Path, PurePosixPath
from urllib.parse import urljoin, urlsplit

import urllib3

from .models import Limits, Outcome, PreviewError


class Budget:
    def __init__(self, limits: Limits, directory: Path):
        self.limits = limits
        self.directory = directory
        self.started = time.monotonic()
        self.bytes_read = 0
        self.extracted_bytes = 0
        self.archive_entries = 0
        self.output_bytes = 0

    def publish(self, size):
        self.check()
        if self.output_bytes + size > self.limits.output_bytes:
            raise PreviewError(Outcome.OVER_LIMIT, "Total derivative output limit exceeded")
        self.output_bytes += size

    def check(self):
        if time.monotonic() - self.started >= self.limits.seconds:
            raise PreviewError(Outcome.OVER_LIMIT, "Processing time limit exceeded")
        size = sum(p.stat().st_size for p in self.directory.rglob("*") if p.is_file())
        if size > self.limits.temporary_bytes:
            raise PreviewError(Outcome.OVER_LIMIT, "Temporary storage limit exceeded")

    def read(self, size):
        self.bytes_read += size
        if self.bytes_read > self.limits.download_bytes:
            raise PreviewError(Outcome.OVER_LIMIT, "Download limit exceeded")
        self.check()


def public_address(url: str) -> tuple[str, str, int, str]:
    """Resolve once and pin the connection to a public address (including redirects)."""
    parsed = urlsplit(url)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
    ):
        raise PreviewError(Outcome.INVALID, "Source must be a public HTTP(S) URL")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    if port not in {80, 443}:
        raise PreviewError(Outcome.INVALID, "Unsupported source port")
    addresses = sorted(
        {item[4][0] for item in socket.getaddrinfo(parsed.hostname, port, type=socket.SOCK_STREAM)}
    )
    if not addresses or any(not ipaddress.ip_address(ip).is_global for ip in addresses):
        raise PreviewError(Outcome.INVALID, "Non-public source address")
    return parsed.scheme, parsed.hostname, port, addresses[0]


def download(url: str, target: Path, budget: Budget, host_guard=None) -> str:
    """Stream a file; never let a driver follow unvalidated network references."""
    for _ in range(6):
        budget.check()
        scheme, host, port, address = public_address(url)
        parsed = urlsplit(url)
        kwargs = {"timeout": urllib3.Timeout(connect=10, read=20), "retries": False}
        if scheme == "https":
            pool = urllib3.HTTPSConnectionPool(
                address,
                port,
                server_hostname=host,
                assert_hostname=host,
                cert_reqs=ssl.CERT_REQUIRED,
                **kwargs,
            )
        else:
            pool = urllib3.HTTPConnectionPool(address, port, **kwargs)
        guard = host_guard(host) if host_guard else nullcontext()
        stack = ExitStack()
        try:
            stack.enter_context(guard)
            response = pool.urlopen(
                "GET",
                parsed.path + ("?" + parsed.query if parsed.query else ""),
                headers={
                    "Host": host,
                    "Accept-Encoding": "identity",
                    "User-Agent": "BTAA-preview/1",
                },
                preload_content=False,
                redirect=False,
            )
            try:
                if response.status in {301, 302, 303, 307, 308}:
                    location = response.headers.get("Location")
                    if not location:
                        raise PreviewError(Outcome.UNAVAILABLE, "Redirect missing location")
                    url = urljoin(url, location)
                    continue
                if response.status != 200:
                    raise PreviewError(Outcome.UNAVAILABLE, f"Source HTTP {response.status}")
                length = response.headers.get("Content-Length")
                if length and int(length) > budget.limits.download_bytes - budget.bytes_read:
                    raise PreviewError(Outcome.OVER_LIMIT, "Source exceeds download limit")
                digest = hashlib.sha256()
                with target.open("wb") as output:
                    for chunk in response.stream(1 << 18, decode_content=False):
                        budget.read(len(chunk))
                        digest.update(chunk)
                        output.write(chunk)
                return digest.hexdigest()
            finally:
                response.close()
        finally:
            stack.close()
            pool.close()
    raise PreviewError(Outcome.UNAVAILABLE, "Too many redirects")


def extract_zip(source: Path, destination: Path, budget: Budget) -> list[Path]:
    destination.mkdir()
    files = []
    total = 0
    with zipfile.ZipFile(source) as archive:
        members = archive.infolist()
        budget.archive_entries += len(members)
        if budget.archive_entries > budget.limits.archive_entries:
            raise PreviewError(Outcome.OVER_LIMIT, "Archive entry limit exceeded")
        if (
            sum(m.file_size for m in members)
            > budget.limits.extracted_bytes - budget.extracted_bytes
        ):
            raise PreviewError(Outcome.OVER_LIMIT, "Archive expansion limit exceeded")
        seen = set()
        for member in members:
            name = PurePosixPath(member.filename)
            mode = member.external_attr >> 16
            if (
                name.is_absolute()
                or ".." in name.parts
                or "\\" in member.filename
                or ":" in member.filename
                or stat.S_ISLNK(mode)
            ):
                raise PreviewError(Outcome.INVALID, "Unsafe archive entry")
            if member.flag_bits & 1:
                raise PreviewError(Outcome.UNSUPPORTED, "Encrypted archive")
            if member.is_dir():
                continue
            if str(name).casefold() in seen:
                raise PreviewError(Outcome.INVALID, "Duplicate archive path")
            seen.add(str(name).casefold())
            target = destination / str(name)
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as inp, target.open("wb") as out:
                while chunk := inp.read(1 << 18):
                    total += len(chunk)
                    budget.extracted_bytes += len(chunk)
                    if budget.extracted_bytes > budget.limits.extracted_bytes:
                        raise PreviewError(Outcome.OVER_LIMIT, "Archive expansion limit exceeded")
                    budget.check()
                    out.write(chunk)
            if zipfile.is_zipfile(target) or target.suffix.lower() in {
                ".tar",
                ".gz",
                ".bz2",
                ".7z",
                ".rar",
                ".tgz",
                ".xz",
            }:
                raise PreviewError(Outcome.UNSUPPORTED, "Nested archives are unsupported")
            files.append(target)
    return files
