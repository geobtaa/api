"""Bounded source retrieval and extraction, independent of web request handlers."""

import hashlib
import io
import ipaddress
import re
import socket
import ssl
import stat
import time
import zipfile
from collections import OrderedDict
from contextlib import ExitStack, contextmanager, nullcontext
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


@contextmanager
def source_response(url, budget, host_guard=None, headers=None):
    """A pinned, guarded request, revalidating every redirect before connecting."""
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
                    **(headers or {}),
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
                yield response, url
                return
            finally:
                response.close()
        finally:
            stack.close()
            pool.close()
    raise PreviewError(Outcome.UNAVAILABLE, "Too many redirects")


def download(url: str, target: Path, budget: Budget, host_guard=None) -> str:
    """Stream a file; never let a driver follow unvalidated network references."""
    with source_response(url, budget, host_guard) as (response, _):
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


class RangeReader(io.RawIOBase):
    """Seekable, bounded HTTP access without exposing URLs to GDAL drivers.

    Each block must belong to the same strongly validated source representation.
    Servers without Range/strong ETag support fall back to bounded download at
    the adapter level. Cache eviction does not reset the downloaded byte budget.
    """

    BLOCK = 64 * 1024
    CACHE_BLOCKS = 64

    def __init__(self, url, budget, host_guard=None):
        super().__init__()
        self.url, self.budget, self.host_guard = url, budget, host_guard
        self.position, self.size = 0, None
        self.etag, self.final_url = None, None
        self.failure = None
        self.cache = OrderedDict()
        self._block(0)

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.position

    def seek(self, offset, whence=0):
        self._checkClosed()
        position = offset + (self.position if whence == 1 else self.size if whence == 2 else 0)
        if whence not in {0, 1, 2} or position < 0:
            raise ValueError("Invalid source seek")
        self.position = position
        return position

    @property
    def fingerprint(self):
        from .models import fingerprint

        return fingerprint({"url": self.final_url, "etag": self.etag, "length": self.size})

    def read_at(self, offset, length):
        try:
            self.seek(offset)
            return self.read(length)
        except PreviewError as exc:
            # GDAL's C callbacks can wrap Python errors. Preserve the precise
            # outcome so a byte limit is not reported as a malformed raster.
            self.failure = exc
            raise

    def _block(self, offset):
        if offset in self.cache:
            self.cache.move_to_end(offset)
            return self.cache[offset]
        end = offset + self.BLOCK - 1
        if self.size is not None:
            end = min(end, self.size - 1)
        headers = {"Range": f"bytes={offset}-{end}"}
        if self.etag:
            headers["If-Match"] = self.etag
        with source_response(self.url, self.budget, self.host_guard, headers) as (response, url):
            if response.status in {200, 405, 416} and self.size is None:
                raise PreviewError(Outcome.UNSUPPORTED, "Source does not support byte ranges")
            if response.status != 206:
                raise PreviewError(Outcome.UNAVAILABLE, f"Range source HTTP {response.status}")
            match = re.fullmatch(
                r"bytes (\d+)-(\d+)/(\d+)", response.headers.get("Content-Range", "")
            )
            if not match:
                raise PreviewError(Outcome.INVALID, "Malformed Content-Range")
            start, stop, size = map(int, match.groups())
            if start != offset or stop != min(end, size - 1) or size <= 0:
                raise PreviewError(Outcome.INVALID, "Incorrect source byte range")
            if response.headers.get("Content-Encoding", "identity").lower() != "identity":
                raise PreviewError(Outcome.INVALID, "Encoded source byte range")
            etag = response.headers.get("ETag", "")
            if not re.fullmatch(r'"[^"\r\n]+"', etag):
                raise PreviewError(Outcome.UNSUPPORTED, "Range source needs a strong ETag")
            if self.size is not None and (size, etag, url) != (
                self.size,
                self.etag,
                self.final_url,
            ):
                raise PreviewError(Outcome.INVALID, "Source changed during partial reads")
            self.size, self.etag, self.final_url = size, etag, url
            expected = stop - start + 1
            if expected > self.budget.limits.download_bytes - self.budget.bytes_read:
                raise PreviewError(Outcome.OVER_LIMIT, "Download limit exceeded")
            chunks, received = [], 0
            for chunk in response.stream(min(expected + 1, 1 << 16), decode_content=False):
                self.budget.read(len(chunk))
                received += len(chunk)
                if received > expected:
                    raise PreviewError(Outcome.INVALID, "Oversized byte range response")
                chunks.append(chunk)
            if received != expected:
                raise PreviewError(Outcome.INVALID, "Truncated byte range response")
            block = b"".join(chunks)
        self.cache[offset] = block
        if len(self.cache) > self.CACHE_BLOCKS:
            self.cache.popitem(last=False)
        return block

    def read(self, size=-1):
        self._checkClosed()
        if size is None or size < 0:
            size = self.size - self.position
        size = max(0, min(size, self.size - self.position))
        if size > self.budget.limits.memory_bytes // 4:
            raise PreviewError(Outcome.OVER_LIMIT, "Source read exceeds memory budget")
        output = bytearray()
        while len(output) < size:
            offset = self.position // self.BLOCK * self.BLOCK
            block = self._block(offset)
            start = self.position - offset
            chunk = block[start : start + size - len(output)]
            output.extend(chunk)
            self.position += len(chunk)
        return bytes(output)

    def readinto(self, buffer):
        chunk = self.read(len(buffer))
        buffer[: len(chunk)] = chunk
        return len(chunk)


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
