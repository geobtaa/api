from __future__ import annotations

from btaa_geo_api_cli.analytics import CommandAnalytics
from btaa_geo_api_cli.config import CliConfig


class FakeClient:
    def __init__(self):
        self.payloads = []

    def post(self, path, *, json):
        self.payloads.append((path, json))
        return {"status": "accepted"}


def test_command_analytics_redacts_api_key_and_output_path():
    client = FakeClient()
    analytics = CommandAnalytics(CliConfig(api_key="secret", client_instance="one"))
    analytics.command = "download"

    analytics.record_event(
        client,
        "cli.command.download",
        properties={"api_key": "secret", "output_path": "/tmp/private/file", "bytes": 10},
    )

    payload = client.payloads[0][1]
    props = payload["events"][0]["properties"]
    assert "api_key" not in props
    assert "output_path" not in props
    assert props["bytes"] == 10


def test_analytics_opt_out_sends_nothing():
    client = FakeClient()
    analytics = CommandAnalytics(CliConfig(analytics_enabled=False))

    analytics.record_event(client, "cli.command.schema")

    assert client.payloads == []
