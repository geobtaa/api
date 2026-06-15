from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any, Iterable, Mapping
from urllib.parse import quote, urljoin
from xml.etree import ElementTree as ET

import redis.asyncio as redis

from app.services.cache_service import (
    CACHE_ROOT,
    REDIS_DB,
    REDIS_HOST,
    REDIS_PASSWORD,
    REDIS_PORT,
    REDIS_TIMEOUT_SECONDS,
)
from db.database import database

logger = logging.getLogger(__name__)

SITEMAP_NAMESPACE = f"{CACHE_ROOT}:sitemap"
SITEMAP_MANIFEST_KEY = f"{SITEMAP_NAMESPACE}:manifest"
SITEMAP_DOC_KEY_PREFIX = f"{SITEMAP_NAMESPACE}:doc:"
SITEMAP_XML_NAMESPACE = "http://www.sitemaps.org/schemas/sitemap/0.9"
SITEMAP_ROOT_NAME = "sitemap.xml"
SITEMAP_PART_RE = re.compile(r"^sitemap-\d+\.xml$")
NOINDEX_ROBOTS_TAG = "noindex, nofollow, noarchive, nosnippet"

SITEMAP_CACHE_TTL_SECONDS = int(os.getenv("SITEMAP_CACHE_TTL_SECONDS", "172800"))
SITEMAP_MAX_URLS_PER_FILE = int(os.getenv("SITEMAP_MAX_URLS_PER_FILE", "50000"))
SITEMAP_DB_BATCH_SIZE = int(os.getenv("SITEMAP_DB_BATCH_SIZE", "5000"))

STATIC_SITE_PATHS = ("/", "/search", "/map")

PUBLISHED_RESOURCES_SQL = """
    SELECT
        id,
        COALESCE(
            "gbl_mdModified_dt",
            "b1g_lastHarvested_dt",
            date_modified_dtsi,
            "b1g_dateAccessioned_dt",
            date_created_dtsi
        ) AS lastmod
    FROM resources
    WHERE
        COALESCE(gbl_suppressed_b, FALSE) = FALSE
        AND LOWER(
            COALESCE(
                NULLIF(b1g_publication_state_s, ''),
                NULLIF(publication_state, ''),
                'published'
            )
        ) = 'published'
        AND id > :last_id
    ORDER BY id
    LIMIT :limit
"""


@dataclass(frozen=True)
class SitemapUrl:
    loc: str
    lastmod: str | None = None


@dataclass(frozen=True)
class SitemapBuildResult:
    application_url: str
    generated_at: str
    documents: dict[str, str]
    part_names: list[str]
    resource_count: int
    static_count: int
    total_url_count: int
    root_is_index: bool

    def manifest(self, stored: bool) -> dict[str, Any]:
        return {
            "application_url": self.application_url,
            "generated_at": self.generated_at,
            "part_names": self.part_names,
            "resource_count": self.resource_count,
            "static_count": self.static_count,
            "total_url_count": self.total_url_count,
            "root_is_index": self.root_is_index,
            "stored": stored,
        }


class SitemapStore:
    def __init__(self) -> None:
        self._redis: redis.Redis | None = None

    def _client(self) -> redis.Redis:
        if self._redis is None:
            self._redis = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                db=REDIS_DB,
                password=REDIS_PASSWORD,
                decode_responses=True,
                socket_timeout=REDIS_TIMEOUT_SECONDS,
                socket_connect_timeout=REDIS_TIMEOUT_SECONDS,
            )
        return self._redis

    async def get_json(self, key: str) -> Any | None:
        try:
            raw = await self._client().get(key)
        except Exception as exc:
            logger.warning("Unable to load sitemap cache key %s: %s", key, exc)
            return None
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Ignoring invalid sitemap cache payload for key %s", key)
            return None

    async def set_json(self, key: str, value: Any, ttl_seconds: int) -> bool:
        try:
            payload = json.dumps(value, separators=(",", ":"), sort_keys=True)
            return bool(await self._client().set(key, payload, ex=ttl_seconds))
        except Exception as exc:
            logger.warning("Unable to store sitemap cache key %s: %s", key, exc)
            return False

    async def delete(self, key: str) -> bool:
        try:
            return bool(await self._client().delete(key))
        except Exception as exc:
            logger.warning("Unable to delete sitemap cache key %s: %s", key, exc)
            return False

    async def close(self) -> None:
        if self._redis is None:
            return
        try:
            await self._redis.aclose()
        except Exception:
            logger.debug("Ignoring sitemap redis close failure", exc_info=True)
        finally:
            self._redis = None


_store = SitemapStore()


def _document_key(name: str) -> str:
    return f"{SITEMAP_DOC_KEY_PREFIX}{name}"


def _application_url(base_url: str | None = None) -> str:
    value = (
        base_url
        or os.getenv("GEOPORTAL_BASE_URL")
        or os.getenv("APPLICATION_URL")
        or "http://localhost:8000"
    ).strip()
    normalized = value.rstrip("/") or "http://localhost:8000"
    for suffix in ("/api/v1", "/api/v1/"):
        if normalized.endswith(suffix):
            return normalized[: -len(suffix)].rstrip("/")
    return normalized


def current_application_url() -> str:
    return _application_url()


def _env_flag(name: str) -> bool | None:
    raw_value = os.getenv(name)
    if raw_value is None:
        return None

    normalized = raw_value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return None


def search_engine_indexing_enabled(indexing_enabled: bool | None = None) -> bool:
    if indexing_enabled is not None:
        return indexing_enabled

    flag = _env_flag("SEARCH_ENGINE_INDEXING_ENABLED")
    if flag is not None:
        return flag

    return False


def build_site_url(base_url: str, path: str) -> str:
    return urljoin(f"{base_url.rstrip('/')}/", path.lstrip("/"))


def _resource_path(resource_id: str) -> str:
    return f"/resources/{quote(str(resource_id), safe=':-._~')}"


def _normalize_lastmod(value: Any) -> str | None:
    if value in (None, ""):
        return None

    if isinstance(value, datetime):
        dt = value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)
        return dt.date().isoformat()

    if isinstance(value, date):
        return value.isoformat()

    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            return parsed.date().isoformat()
        except ValueError:
            return text if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text) else None

    return None


def _sitemap_generated_at() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _render_urlset(entries: Iterable[SitemapUrl]) -> str:
    urlset = ET.Element("urlset", xmlns=SITEMAP_XML_NAMESPACE)
    for entry in entries:
        url_el = ET.SubElement(urlset, "url")
        ET.SubElement(url_el, "loc").text = entry.loc
        if entry.lastmod:
            ET.SubElement(url_el, "lastmod").text = entry.lastmod

    ET.indent(urlset, space="  ")
    return ET.tostring(urlset, encoding="unicode", xml_declaration=True)


def _render_sitemap_index(*, base_url: str, part_names: Iterable[str], generated_at: str) -> str:
    sitemapindex = ET.Element("sitemapindex", xmlns=SITEMAP_XML_NAMESPACE)
    for part_name in part_names:
        sitemap_el = ET.SubElement(sitemapindex, "sitemap")
        ET.SubElement(sitemap_el, "loc").text = build_site_url(base_url, f"/sitemaps/{part_name}")
        ET.SubElement(sitemap_el, "lastmod").text = generated_at

    ET.indent(sitemapindex, space="  ")
    return ET.tostring(sitemapindex, encoding="unicode", xml_declaration=True)


def build_x_robots_tag(indexing_enabled: bool | None = None) -> str | None:
    if search_engine_indexing_enabled(indexing_enabled=indexing_enabled):
        return None
    return NOINDEX_ROBOTS_TAG


def build_robots_txt(base_url: str | None = None, indexing_enabled: bool | None = None) -> str:
    if not search_engine_indexing_enabled(indexing_enabled=indexing_enabled):
        return "\n".join(
            [
                "# Block all search engine bots from indexing",
                "User-agent: *",
                "Disallow: /",
                "",
                "# Explicitly block major bots",
                "User-agent: Googlebot",
                "Disallow: /",
                "",
                "User-agent: Bingbot",
                "Disallow: /",
                "",
                "User-agent: Slurp",
                "Disallow: /",
                "",
                "User-agent: DuckDuckBot",
                "Disallow: /",
                "",
                "User-agent: Baiduspider",
                "Disallow: /",
                "",
                "User-agent: YandexBot",
                "Disallow: ",
                "",
            ]
        )

    app_url = _application_url(base_url)
    lines = [
        "# Production robots rules for the BTAA Geoportal.",
        "User-agent: *",
        "Allow: /",
        "Disallow: /api/",
        "Disallow: /bookmarks",
        "Disallow: /home/blog-posts",
        "Disallow: /iiif/manifest",
        "Disallow: /map/h3",
        "# Search result pages and faceted/paginated variants.",
        "Disallow: /search?",
        "Disallow: /search?q=",
        "Disallow: /search?adv_q=",
        "Disallow: /search?include_filters",
        "Disallow: /search?exclude_filters",
        "Disallow: /search?fq[",
        "Disallow: /search?page=",
        "Disallow: /search?per_page=",
        "Disallow: /search?sort=",
        "Disallow: /search?view=",
        "Disallow: /search?showAdvanced=",
        "Disallow: /search/facets/",
        "Disallow: /suggest",
        "Disallow: /test",
        f"Sitemap: {build_site_url(app_url, '/sitemap.xml')}",
    ]
    return "\n".join(lines) + "\n"


def build_sitemap_documents(
    *,
    base_url: str,
    resource_rows: Iterable[Mapping[str, Any]],
    generated_at: str | None = None,
    max_urls_per_file: int = SITEMAP_MAX_URLS_PER_FILE,
) -> SitemapBuildResult:
    app_url = _application_url(base_url)
    created_at = generated_at or _sitemap_generated_at()

    chunk_size = max(1, int(max_urls_per_file))
    chunks: list[list[SitemapUrl]] = []
    current_chunk: list[SitemapUrl] = []

    def append_entry(entry: SitemapUrl) -> None:
        nonlocal current_chunk
        current_chunk.append(entry)
        if len(current_chunk) >= chunk_size:
            chunks.append(current_chunk)
            current_chunk = []

    for path in STATIC_SITE_PATHS:
        append_entry(SitemapUrl(loc=build_site_url(app_url, path)))

    resource_count = 0
    for row in resource_rows:
        resource_id = row.get("id")
        if not resource_id:
            continue
        append_entry(
            SitemapUrl(
                loc=build_site_url(app_url, _resource_path(str(resource_id))),
                lastmod=_normalize_lastmod(row.get("lastmod")),
            )
        )
        resource_count += 1

    if current_chunk:
        chunks.append(current_chunk)

    if not chunks:
        chunks = [[SitemapUrl(loc=build_site_url(app_url, "/"))]]

    documents: dict[str, str] = {}
    part_names: list[str] = []

    if len(chunks) == 1:
        documents[SITEMAP_ROOT_NAME] = _render_urlset(chunks[0])
        root_is_index = False
    else:
        for index, chunk in enumerate(chunks, start=1):
            part_name = f"sitemap-{index}.xml"
            part_names.append(part_name)
            documents[part_name] = _render_urlset(chunk)
        documents[SITEMAP_ROOT_NAME] = _render_sitemap_index(
            base_url=app_url,
            part_names=part_names,
            generated_at=created_at,
        )
        root_is_index = True

    static_count = len(STATIC_SITE_PATHS)
    return SitemapBuildResult(
        application_url=app_url,
        generated_at=created_at,
        documents=documents,
        part_names=part_names,
        resource_count=resource_count,
        static_count=static_count,
        total_url_count=static_count + resource_count,
        root_is_index=root_is_index,
    )


async def _fetch_published_resource_rows(
    *, batch_size: int = SITEMAP_DB_BATCH_SIZE
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    last_id = ""
    limit = max(1, int(batch_size))

    while True:
        batch = await database.fetch_all(
            query=PUBLISHED_RESOURCES_SQL,
            values={"last_id": last_id, "limit": limit},
        )
        if not batch:
            break
        mapped = [dict(row) for row in batch]
        rows.extend(mapped)
        last_id = str(mapped[-1]["id"])

    return rows


async def generate_and_store(
    *,
    base_url: str | None = None,
    max_urls_per_file: int = SITEMAP_MAX_URLS_PER_FILE,
    batch_size: int = SITEMAP_DB_BATCH_SIZE,
    ttl_seconds: int = SITEMAP_CACHE_TTL_SECONDS,
) -> tuple[SitemapBuildResult, bool]:
    result = build_sitemap_documents(
        base_url=_application_url(base_url),
        resource_rows=await _fetch_published_resource_rows(batch_size=batch_size),
        max_urls_per_file=max_urls_per_file,
    )
    stored = await store_sitemap_documents(result, ttl_seconds=ttl_seconds)
    return result, stored


async def store_sitemap_documents(
    result: SitemapBuildResult, *, ttl_seconds: int = SITEMAP_CACHE_TTL_SECONDS
) -> bool:
    existing_manifest = await _store.get_json(SITEMAP_MANIFEST_KEY) or {}
    existing_docs = {
        SITEMAP_ROOT_NAME,
        *existing_manifest.get("part_names", []),
    }

    stored_ok = True
    for name, xml_content in result.documents.items():
        stored_ok = (
            await _store.set_json(_document_key(name), {"content": xml_content}, ttl_seconds)
            and stored_ok
        )

    for stale_name in existing_docs - set(result.documents):
        await _store.delete(_document_key(stale_name))

    manifest = result.manifest(stored=stored_ok)
    manifest_ok = await _store.set_json(SITEMAP_MANIFEST_KEY, manifest, ttl_seconds)
    return stored_ok and manifest_ok


async def get_sitemap_manifest() -> dict[str, Any] | None:
    return await _store.get_json(SITEMAP_MANIFEST_KEY)


async def get_current_sitemap_document(name: str) -> str | None:
    manifest = await get_sitemap_manifest()
    if isinstance(manifest, dict) and manifest.get("application_url") != current_application_url():
        logger.info(
            "Ignoring cached sitemap %s generated for application_url=%s",
            name,
            manifest.get("application_url"),
        )
        return None
    return await get_sitemap_document(name)


async def get_sitemap_document(name: str) -> str | None:
    payload = await _store.get_json(_document_key(name))
    if isinstance(payload, dict):
        content = payload.get("content")
        if isinstance(content, str):
            return content
    return None


def is_valid_sitemap_part_name(name: str) -> bool:
    return bool(SITEMAP_PART_RE.fullmatch(name))


async def close_store() -> None:
    await _store.close()
