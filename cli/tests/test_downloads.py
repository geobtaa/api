from __future__ import annotations

from pathlib import Path

import httpx
from conftest import invoke


def test_download_best_streams_file(runner, monkeypatch, tmp_path: Path):
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/api/v1/resources/b1g_test/downloads":
            return httpx.Response(
                200,
                json={"downloads": [{"label": "test.geojson", "url": "/files/test.geojson"}]},
            )
        if request.url.path == "/api/v1/files/test.geojson":
            return httpx.Response(200, content=b"{}")
        if request.url.path == "/api/v1/analytics/events":
            return httpx.Response(202, json={"status": "accepted"})
        return httpx.Response(404)

    from btaa_geo_api_cli import app as app_module
    from btaa_geo_api_cli.client import BtaaApiClient

    class MockClient(BtaaApiClient):
        def __init__(self, config, *args, **kwargs):
            super().__init__(config, transport=httpx.MockTransport(handler))

    monkeypatch.setattr(app_module, "BtaaApiClient", MockClient)

    result = invoke(
        runner, ["--no-analytics", "download", "b1g_test", "--best", "--out", str(tmp_path)]
    )

    assert result.exit_code == 0, result.output
    assert (tmp_path / "test.geojson").read_bytes() == b"{}"


def test_download_no_clobber_blocks_existing_file(runner, mock_client, tmp_path: Path):
    (tmp_path / "test.geojson").write_text("old", encoding="utf-8")
    mock_client(
        {
            "/api/v1/resources/b1g_test/downloads": {
                "downloads": [{"label": "test.geojson", "url": "/files/test.geojson"}]
            }
        }
    )

    result = invoke(
        runner,
        [
            "--no-analytics",
            "download",
            "b1g_test",
            "--best",
            "--out",
            str(tmp_path),
            "--no-clobber",
        ],
    )

    assert result.exit_code != 0
    assert "Output exists" in result.output
