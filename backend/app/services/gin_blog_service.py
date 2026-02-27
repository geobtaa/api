from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional, TypedDict

import requests
import yaml
from sqlalchemy import and_, desc, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from db.database import database
from db.models import gin_blog_posts

logger = logging.getLogger(__name__)

GITHUB_API_ROOT = "https://api.github.com/repos/geobtaa/geobtaa.github.io/contents"
RAW_IMAGE_ROOT = (
    "https://raw.githubusercontent.com/geobtaa/geobtaa.github.io/main/src/assets/images"
)
GIN_SITE_ROOT = "https://gin.btaa.org"
REQUEST_TIMEOUT_SECONDS = 30


class NormalizedBlogPost(TypedDict):
    slug: str
    source_path: str
    url: str
    title: str
    excerpt: str
    published_at: datetime
    category: str
    authors_json: List[str]
    tags_json: List[str]
    image_url: Optional[str]
    image_alt: Optional[str]
    source_sha: Optional[str]


class GINBlogService:
    def _list_content_files(self, path: str) -> List[Dict[str, Any]]:
        response = requests.get(f"{GITHUB_API_ROOT}/{path}", timeout=REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, list):
            return []
        return [
            item
            for item in data
            if item.get("type") == "file" and item.get("name", "").endswith(".mdx")
        ]

    def _fetch_raw_content(self, raw_url: str) -> str:
        response = requests.get(raw_url, timeout=REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
        return response.text

    def _parse_frontmatter(self, raw_content: str) -> tuple[Dict[str, Any], str]:
        if not raw_content.startswith("---"):
            return {}, raw_content
        lines = raw_content.splitlines()
        end_index = None
        for idx in range(1, len(lines)):
            if lines[idx].strip() == "---":
                end_index = idx
                break
        if end_index is None:
            return {}, raw_content
        frontmatter_str = "\n".join(lines[1:end_index])
        body_str = "\n".join(lines[end_index + 1 :])
        parsed = yaml.safe_load(frontmatter_str) or {}
        if not isinstance(parsed, dict):
            return {}, body_str
        return parsed, body_str

    def _normalize_date(self, value: Any) -> Optional[datetime]:
        if isinstance(value, datetime):
            return value.replace(tzinfo=None)
        if isinstance(value, date):
            return datetime(value.year, value.month, value.day)
        if isinstance(value, str):
            raw = value.strip().replace("Z", "+00:00")
            try:
                return datetime.fromisoformat(raw).replace(tzinfo=None)
            except ValueError:
                return None
        return None

    def _normalize_authors(self, value: Any) -> List[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [value.strip()] if value.strip() else []
        if isinstance(value, list):
            names: List[str] = []
            for item in value:
                if isinstance(item, str) and item.strip():
                    names.append(item.strip())
                elif isinstance(item, dict):
                    name = item.get("name")
                    if isinstance(name, str) and name.strip():
                        names.append(name.strip())
            return names
        if isinstance(value, dict):
            name = value.get("name")
            if isinstance(name, str) and name.strip():
                return [name.strip()]
        return []

    def _normalize_tags(self, value: Any) -> List[str]:
        if not isinstance(value, list):
            return []
        tags: List[str] = []
        for tag in value:
            if isinstance(tag, str) and tag.strip():
                tags.append(tag.strip())
        return tags

    def _normalize_cover(self, value: Any) -> tuple[Optional[str], Optional[str]]:
        if not isinstance(value, dict):
            return None, None
        alt = value.get("alt")
        image = value.get("image")
        image_url: Optional[str] = None
        if isinstance(image, str):
            if image.startswith("@images/"):
                image_url = f"{RAW_IMAGE_ROOT}/{image.replace('@images/', '', 1)}"
            elif image.startswith("/"):
                image_url = f"{GIN_SITE_ROOT}{image}"
            elif image.startswith("http://") or image.startswith("https://"):
                image_url = image
        return image_url, alt if isinstance(alt, str) else None

    def _extract_excerpt(self, frontmatter: Dict[str, Any], body: str) -> str:
        explicit = frontmatter.get("excerpt")
        if isinstance(explicit, str) and explicit.strip():
            return explicit.strip()
        for line in body.splitlines():
            content = line.strip()
            if content and not content.startswith("import ") and not content.startswith("!["):
                return content[:300]
        return ""

    def _category_for_path(self, source_path: str) -> str:
        return "update" if "/updates/" in source_path else "post"

    def _url_for_slug(self, slug: str, category: str) -> str:
        route = "updates" if category == "update" else "posts"
        return f"{GIN_SITE_ROOT}/{route}/{slug}/"

    def _normalize_item(
        self, item: Dict[str, Any], raw_content: str
    ) -> Optional[NormalizedBlogPost]:
        source_path = str(item.get("path") or "")
        slug = source_path.split("/")[-1].replace(".mdx", "")
        if not source_path or not slug:
            return None

        frontmatter, body = self._parse_frontmatter(raw_content)
        if bool(frontmatter.get("draft")):
            return None

        title = frontmatter.get("title")
        if not isinstance(title, str) or not title.strip():
            return None

        category = self._category_for_path(source_path)
        published_at = self._normalize_date(frontmatter.get("date"))
        if published_at is None:
            return None

        excerpt = self._extract_excerpt(frontmatter, body)
        image_url, image_alt = self._normalize_cover(frontmatter.get("cover"))
        authors = self._normalize_authors(frontmatter.get("authors"))
        tags = self._normalize_tags(frontmatter.get("tags"))

        return {
            "slug": slug,
            "source_path": source_path,
            "url": self._url_for_slug(slug, category),
            "title": title.strip(),
            "excerpt": excerpt,
            "published_at": published_at,
            "category": category,
            "authors_json": authors,
            "tags_json": tags,
            "image_url": image_url,
            "image_alt": image_alt,
            "source_sha": item.get("sha"),
        }

    async def sync_posts_from_github(self) -> Dict[str, Any]:
        discovered: List[NormalizedBlogPost] = []
        for path in ("src/content/docs/posts", "src/content/docs/updates"):
            files = self._list_content_files(path)
            for item in files:
                raw_url = item.get("download_url")
                if not isinstance(raw_url, str) or not raw_url:
                    continue
                try:
                    raw_content = self._fetch_raw_content(raw_url)
                    normalized = self._normalize_item(item, raw_content)
                    if normalized:
                        discovered.append(normalized)
                except Exception as err:
                    logger.warning("GIN blog sync skipped %s: %s", item.get("path"), err)

        synced_at = datetime.utcnow()
        upserted = 0
        discovered_slugs = [item["slug"] for item in discovered]

        for item in discovered:
            stmt = pg_insert(gin_blog_posts).values(
                slug=item["slug"],
                source_path=item["source_path"],
                url=item["url"],
                title=item["title"],
                excerpt=item["excerpt"],
                published_at=item["published_at"],
                category=item["category"],
                authors_json=item["authors_json"],
                tags_json=item["tags_json"],
                image_url=item["image_url"],
                image_alt=item["image_alt"],
                source_sha=item["source_sha"],
                synced_at=synced_at,
                is_active=True,
                updated_at=synced_at,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=[gin_blog_posts.c.slug],
                set_={
                    "source_path": stmt.excluded.source_path,
                    "url": stmt.excluded.url,
                    "title": stmt.excluded.title,
                    "excerpt": stmt.excluded.excerpt,
                    "published_at": stmt.excluded.published_at,
                    "category": stmt.excluded.category,
                    "authors_json": stmt.excluded.authors_json,
                    "tags_json": stmt.excluded.tags_json,
                    "image_url": stmt.excluded.image_url,
                    "image_alt": stmt.excluded.image_alt,
                    "source_sha": stmt.excluded.source_sha,
                    "synced_at": stmt.excluded.synced_at,
                    "is_active": True,
                    "updated_at": synced_at,
                },
            )
            await database.execute(stmt)
            upserted += 1

        deactivated = 0
        if discovered_slugs:
            deactivate_stmt = (
                update(gin_blog_posts)
                .where(
                    and_(
                        gin_blog_posts.c.is_active.is_(True),
                        gin_blog_posts.c.slug.notin_(discovered_slugs),
                    )
                )
                .values(is_active=False, updated_at=synced_at)
            )
            deactivated = int(await database.execute(deactivate_stmt) or 0)

        return {
            "discovered": len(discovered),
            "upserted": upserted,
            "deactivated": max(deactivated, 0),
            "synced_at": synced_at.isoformat(),
        }

    async def list_home_posts(
        self,
        *,
        limit: int,
        pinned_slugs: List[str],
        tag: Optional[str] = None,
    ) -> Dict[str, Any]:
        query = (
            select(gin_blog_posts)
            .where(gin_blog_posts.c.is_active.is_(True))
            .order_by(desc(gin_blog_posts.c.published_at))
            .limit(200)
        )
        rows = await database.fetch_all(query)
        records = [dict(r) for r in rows]

        if tag:
            tag_lower = tag.strip().lower()

            def has_tag(rec: Dict[str, Any]) -> bool:
                tags = rec.get("tags_json") or []
                return any(isinstance(t, str) and t.lower() == tag_lower for t in tags)

            records = [record for record in records if has_tag(record)]

        pinned_map = {record["slug"]: record for record in records}
        pinned: List[Dict[str, Any]] = []
        for slug in pinned_slugs:
            entry = pinned_map.get(slug)
            if entry:
                pinned.append(entry)

        pinned_set = {record["slug"] for record in pinned}
        remaining = [record for record in records if record["slug"] not in pinned_set]
        ordered = (pinned + remaining)[:limit]

        def serialize(record: Dict[str, Any]) -> Dict[str, Any]:
            return {
                "slug": record.get("slug"),
                "url": record.get("url"),
                "title": record.get("title"),
                "excerpt": record.get("excerpt"),
                "published_at": record.get("published_at"),
                "category": record.get("category"),
                "authors": list(record.get("authors_json") or []),
                "tags": list(record.get("tags_json") or []),
                "image_url": record.get("image_url"),
                "image_alt": record.get("image_alt"),
            }

        return {
            "data": [serialize(record) for record in ordered],
            "meta": {
                "pinned_slugs": [slug for slug in pinned_slugs if slug in pinned_set],
                "total_count": len(records),
                "fetched_at": datetime.utcnow().isoformat(),
            },
        }

    def fetch_live_home_posts(
        self,
        *,
        limit: int,
        pinned_slugs: List[str],
        tag: Optional[str] = None,
    ) -> Dict[str, Any]:
        discovered: List[Dict[str, Any]] = []
        for path in ("src/content/docs/posts", "src/content/docs/updates"):
            try:
                files = self._list_content_files(path)
            except Exception as err:
                logger.warning("GIN live fetch failed listing %s: %s", path, err)
                continue
            for item in files:
                raw_url = item.get("download_url")
                if not isinstance(raw_url, str) or not raw_url:
                    continue
                try:
                    raw_content = self._fetch_raw_content(raw_url)
                    normalized = self._normalize_item(item, raw_content)
                    if not normalized:
                        continue
                    discovered.append(
                        {
                            "slug": normalized["slug"],
                            "url": normalized["url"],
                            "title": normalized["title"],
                            "excerpt": normalized["excerpt"],
                            "published_at": normalized["published_at"],
                            "category": normalized["category"],
                            "authors": list(normalized["authors_json"]),
                            "tags": list(normalized["tags_json"]),
                            "image_url": normalized["image_url"],
                            "image_alt": normalized["image_alt"],
                        }
                    )
                except Exception as err:
                    logger.warning("GIN live fetch skipped %s: %s", item.get("path"), err)

        discovered.sort(key=lambda item: item.get("published_at") or datetime.min, reverse=True)

        if tag:
            tag_lower = tag.strip().lower()
            discovered = [
                record
                for record in discovered
                if any(
                    isinstance(value, str) and value.lower() == tag_lower
                    for value in (record.get("tags") or [])
                )
            ]

        pinned_map = {record["slug"]: record for record in discovered}
        pinned: List[Dict[str, Any]] = []
        for slug in pinned_slugs:
            entry = pinned_map.get(slug)
            if entry:
                pinned.append(entry)

        pinned_set = {record["slug"] for record in pinned}
        remaining = [record for record in discovered if record["slug"] not in pinned_set]
        ordered = (pinned + remaining)[:limit]

        return {
            "data": ordered,
            "meta": {
                "pinned_slugs": [slug for slug in pinned_slugs if slug in pinned_set],
                "total_count": len(discovered),
                "fetched_at": datetime.utcnow().isoformat(),
            },
        }
