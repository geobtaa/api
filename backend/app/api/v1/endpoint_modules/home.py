from functools import lru_cache
from pathlib import Path
from typing import List, Optional

import yaml
from fastapi import APIRouter, Query, Request

from app.api.v1.utils import create_response
from app.services.cache_service import cached_endpoint
from app.services.gin_blog_service import GINBlogService

router = APIRouter()
gin_blog_service = GINBlogService()

HOME_BLOG_CACHE_TTL = 3600  # 1 hour


def _resolve_theme_file() -> Optional[Path]:
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "frontend" / "theme.yaml"
        if candidate.exists():
            return candidate
    return None


@lru_cache(maxsize=1)
def _read_theme_registry() -> dict:
    theme_file = _resolve_theme_file()
    if not theme_file:
        return {}
    try:
        raw = theme_file.read_text(encoding="utf-8")
        parsed = yaml.safe_load(raw) or {}
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _pinned_slugs_for_theme(theme: Optional[str]) -> List[str]:
    registry = _read_theme_registry()
    themes = registry.get("themes")
    if not isinstance(themes, dict):
        return []

    default_theme = registry.get("default_theme")
    theme_id = theme if isinstance(theme, str) and theme in themes else default_theme
    if not isinstance(theme_id, str) or theme_id not in themes:
        return []

    cfg = themes.get(theme_id, {})
    if not isinstance(cfg, dict):
        return []
    homepage_cfg = cfg.get("homepage")
    if not isinstance(homepage_cfg, dict):
        return []
    blog_cfg = homepage_cfg.get("blog")
    if not isinstance(blog_cfg, dict):
        return []
    pinned = blog_cfg.get("pinned_slugs")
    if not isinstance(pinned, list):
        return []
    return [slug for slug in pinned if isinstance(slug, str) and slug.strip()]


@router.get("/home/blog-posts")
@cached_endpoint(ttl=HOME_BLOG_CACHE_TTL, tags=["home", "home_blog"])
async def list_home_blog_posts(
    request: Request,
    limit: int = Query(6, ge=1, le=24),
    theme: Optional[str] = Query(None, description="Theme id from frontend theme registry"),
    tag: Optional[str] = Query(
        None, description="Optional tag filter (exact match, case-insensitive)"
    ),
):
    # Pinned entries are no longer configured via `theme.yaml`.
    # Homepage blog cards should come purely from database ordering by `published_at`.
    resolved_pins: List[str] = []
    try:
        payload = await gin_blog_service.list_home_posts(
            limit=limit,
            pinned_slugs=resolved_pins,
            tag=tag,
        )
    except Exception:
        try:
            payload = gin_blog_service.fetch_live_home_posts(
                limit=limit,
                pinned_slugs=resolved_pins,
                tag=tag,
            )
        except Exception:
            payload = {
                "data": [],
                "meta": {
                    "pinned_slugs": [],
                    "total_count": 0,
                    "fetched_at": None,
                },
            }
    else:
        if int(payload.get("meta", {}).get("total_count", 0)) == 0:
            try:
                payload = gin_blog_service.fetch_live_home_posts(
                    limit=limit,
                    pinned_slugs=resolved_pins,
                    tag=tag,
                )
            except Exception:
                pass
    return create_response(payload)
