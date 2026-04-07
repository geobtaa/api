from __future__ import annotations

import hashlib
import re
import zipfile
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

_SQL_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_WINDOWS_ABSOLUTE_PATH_RE = re.compile(r"^[A-Za-z]:")


def stable_hex_digest(value: str, *, digest_size: int = 16) -> str:
    """Return a stable hex digest without relying on weak hash algorithms."""
    return hashlib.blake2b(value.encode("utf-8"), digest_size=digest_size).hexdigest()


def require_sql_identifier(value: str, *, kind: str = "identifier") -> str:
    """Validate a SQL identifier against a conservative allowlist."""
    if not _SQL_IDENTIFIER_RE.fullmatch(value):
        raise ValueError(f"Unsafe {kind}: {value!r}")
    return value


def quote_sql_identifier(value: str, *, kind: str = "identifier") -> str:
    """Quote a validated SQL identifier."""
    return f'"{require_sql_identifier(value, kind=kind)}"'


def require_safe_filename(value: str, *, kind: str = "filename") -> str:
    """Validate that a filename is a single safe path segment."""
    if not value or value in {".", ".."}:
        raise ValueError(f"Unsafe {kind}: {value!r}")
    if Path(value).name != value:
        raise ValueError(f"Unsafe {kind}: {value!r}")
    if any(sep in value for sep in ("/", "\\", "\x00")):
        raise ValueError(f"Unsafe {kind}: {value!r}")
    return value


def url_hostname_matches(url: str, domain: str) -> bool:
    """Return true when URL hostname matches a domain exactly or as a subdomain."""
    try:
        hostname = (urlparse(url).hostname or "").lower()
    except ValueError:
        return False

    domain = domain.lower()
    return bool(hostname) and (hostname == domain or hostname.endswith(f".{domain}"))


def safe_extract_zip(
    zip_ref: zipfile.ZipFile,
    destination: str | Path,
    *,
    members: Iterable[str] | None = None,
) -> list[Path]:
    """Extract ZIP members only if every target stays inside destination."""
    destination_path = Path(destination).resolve()
    selected = (
        [zip_ref.getinfo(member_name) for member_name in members]
        if members is not None
        else zip_ref.infolist()
    )
    extracted_paths: list[Path] = []

    for info in selected:
        normalized_name = info.filename.replace("\\", "/")
        if (
            normalized_name.startswith("/")
            or _WINDOWS_ABSOLUTE_PATH_RE.match(normalized_name)
            or any(part == ".." for part in Path(normalized_name).parts)
        ):
            raise ValueError(f"Unsafe archive member: {info.filename!r}")

        target_path = (destination_path / normalized_name).resolve()
        if destination_path not in target_path.parents and target_path != destination_path:
            raise ValueError(f"Archive member escapes destination: {info.filename!r}")

        zip_ref.extract(info, destination_path)
        extracted_paths.append(target_path)

    return extracted_paths
