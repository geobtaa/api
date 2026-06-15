from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from typer.testing import CliRunner

from btaa_geo_api_cli.app import app


@pytest.fixture
def runner(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> CliRunner:
    monkeypatch.setenv("BTAA_GEO_API_CONFIG_DIR", str(tmp_path / "config"))
    return CliRunner()


@pytest.fixture
def sample_search_payload() -> dict:
    return {
        "data": [
            {
                "id": "b1g_test",
                "attributes": {
                    "ogm": {
                        "dct_title_s": "Water Test",
                        "gbl_indexYear_im": [2020],
                        "schema_provider_s": "Test University",
                    }
                },
            }
        ],
        "meta": {"totalCount": 1, "totalPages": 1},
    }


class Recorder:
    def __init__(self, payloads: dict[str, object] | None = None):
        self.requests: list[httpx.Request] = []
        self.payloads = payloads or {}

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path
        if path == "/api/v1/analytics/events":
            return httpx.Response(202, json={"status": "accepted"})
        payload = self.payloads.get(path)
        if payload is None:
            payload = {"ok": True}
        if isinstance(payload, str):
            return httpx.Response(200, text=payload, headers={"content-type": "text/plain"})
        return httpx.Response(200, json=payload)


@pytest.fixture
def mock_client(monkeypatch: pytest.MonkeyPatch):
    recorders: list[Recorder] = []

    def install(payloads: dict[str, object] | None = None) -> Recorder:
        recorder = Recorder(payloads)
        recorders.append(recorder)
        from btaa_geo_api_cli import app as app_module
        from btaa_geo_api_cli.client import BtaaApiClient

        class MockClient(BtaaApiClient):
            def __init__(self, config, *args, **kwargs):
                super().__init__(config, transport=httpx.MockTransport(recorder.handler))

        monkeypatch.setattr(app_module, "BtaaApiClient", MockClient)
        return recorder

    return install


def invoke(runner: CliRunner, args: list[str], input: str | None = None):
    return runner.invoke(app, args, input=input)
