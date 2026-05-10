from __future__ import annotations

from btaa_geo_api_cli.config import DEFAULT_BASE_URL, load_config


def test_default_base_url_points_to_production(runner):
    config = load_config()

    assert DEFAULT_BASE_URL == "https://lib-geoportal-prd-web-01.oit.umn.edu/api/v1"
    assert config.base_url == DEFAULT_BASE_URL
