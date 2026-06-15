from datetime import UTC, datetime
from xml.etree import ElementTree as ET

import pytest_asyncio

from app.services.sitemap_service import (
    NOINDEX_ROBOTS_TAG,
    build_robots_txt,
    build_sitemap_documents,
    build_x_robots_tag,
    get_current_sitemap_document,
)

NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_database():
    yield


@pytest_asyncio.fixture(scope="session", autouse=True)
async def db_connection():
    yield


@pytest_asyncio.fixture(autouse=True)
async def db_transaction():
    yield


def _xml_root(xml_text: str) -> ET.Element:
    return ET.fromstring(xml_text)


def test_build_robots_txt_blocks_all_crawlers_when_indexing_is_disabled():
    robots_txt = build_robots_txt("https://geo.example.org", indexing_enabled=False)

    assert robots_txt == "\n".join(
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
    assert "Sitemap:" not in robots_txt


def test_build_robots_txt_includes_public_routes_and_sitemap_url_when_enabled():
    robots_txt = build_robots_txt("https://geo.example.org", indexing_enabled=True)

    assert "User-agent: *" in robots_txt
    assert "Disallow: /api/" in robots_txt
    assert "Disallow: /bookmarks" in robots_txt
    assert "Disallow: /search?" in robots_txt
    assert "Disallow: /search?include_filters" in robots_txt
    assert "Disallow: /search?view=" in robots_txt
    assert "Sitemap: https://geo.example.org/sitemap.xml" in robots_txt


def test_build_robots_txt_strips_api_suffix_from_application_url(monkeypatch):
    monkeypatch.setenv("APPLICATION_URL", "https://geo.example.org/api/v1/")

    robots_txt = build_robots_txt(indexing_enabled=True)

    assert "Sitemap: https://geo.example.org/sitemap.xml" in robots_txt


def test_build_x_robots_tag_disables_indexing_when_feature_flag_is_off():
    assert build_x_robots_tag(indexing_enabled=False) == NOINDEX_ROBOTS_TAG
    assert build_x_robots_tag(indexing_enabled=True) is None


async def test_get_current_sitemap_document_ignores_stale_application_url(monkeypatch):
    async def fake_get_json(key: str):
        if key.endswith(":manifest"):
            return {"application_url": "https://lib-geoportal-prd-web-01.oit.umn.edu"}
        return {"content": "<stale />"}

    monkeypatch.setenv("GEOPORTAL_BASE_URL", "https://geo.btaa.org")
    monkeypatch.setattr("app.services.sitemap_service._store.get_json", fake_get_json)

    assert await get_current_sitemap_document("sitemap.xml") is None


def test_build_sitemap_documents_renders_single_urlset():
    result = build_sitemap_documents(
        base_url="https://geo.example.org",
        resource_rows=[
            {
                "id": "ark:-77981-gmgs8p5v86m",
                "lastmod": datetime(2026, 4, 8, 12, 0, tzinfo=UTC),
            }
        ],
        generated_at="2026-04-08T12:00:00Z",
        max_urls_per_file=50_000,
    )

    assert result.root_is_index is False
    assert result.part_names == []

    root = _xml_root(result.documents["sitemap.xml"])
    assert root.tag == f"{{{NS['sm']}}}urlset"

    urls = root.findall("sm:url", NS)
    locs = [url.findtext("sm:loc", namespaces=NS) for url in urls]

    assert "https://geo.example.org/" in locs
    assert "https://geo.example.org/search" in locs
    assert "https://geo.example.org/map" in locs
    assert "https://geo.example.org/resources/ark:-77981-gmgs8p5v86m" in locs

    resource_url = next(
        url
        for url in urls
        if url.findtext("sm:loc", namespaces=NS)
        == "https://geo.example.org/resources/ark:-77981-gmgs8p5v86m"
    )
    assert resource_url.findtext("sm:lastmod", namespaces=NS) == "2026-04-08"


def test_build_sitemap_documents_splits_large_sets_into_index_and_parts():
    result = build_sitemap_documents(
        base_url="https://geo.example.org",
        resource_rows=[
            {"id": "resource-1", "lastmod": "2026-04-01T10:00:00Z"},
            {"id": "resource-2", "lastmod": "2026-04-02T10:00:00Z"},
        ],
        generated_at="2026-04-08T12:00:00Z",
        max_urls_per_file=4,
    )

    assert result.root_is_index is True
    assert result.part_names == ["sitemap-1.xml", "sitemap-2.xml"]

    index_root = _xml_root(result.documents["sitemap.xml"])
    assert index_root.tag == f"{{{NS['sm']}}}sitemapindex"

    sitemap_locs = [
        node.findtext("sm:loc", namespaces=NS) for node in index_root.findall("sm:sitemap", NS)
    ]
    assert sitemap_locs == [
        "https://geo.example.org/sitemaps/sitemap-1.xml",
        "https://geo.example.org/sitemaps/sitemap-2.xml",
    ]

    first_part = _xml_root(result.documents["sitemap-1.xml"])
    first_part_locs = [
        node.findtext("sm:loc", namespaces=NS) for node in first_part.findall("sm:url", NS)
    ]
    assert first_part_locs == [
        "https://geo.example.org/",
        "https://geo.example.org/search",
        "https://geo.example.org/map",
        "https://geo.example.org/resources/resource-1",
    ]

    second_part = _xml_root(result.documents["sitemap-2.xml"])
    second_part_locs = [
        node.findtext("sm:loc", namespaces=NS) for node in second_part.findall("sm:url", NS)
    ]
    assert second_part_locs == ["https://geo.example.org/resources/resource-2"]
