from __future__ import annotations

from typing import Any, Optional

from app.services.bridge_sync.client import KitheBridgeClient


class FakeResponse:
    status_code = 200

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return {"data": [], "has_more": False, "next_cursor": None}


class FakeSession:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def get(
        self,
        url: str,
        *,
        params: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
        timeout: Optional[int] = None,
        verify: Optional[bool] = None,
    ) -> FakeResponse:
        self.calls.append(
            {
                "url": url,
                "params": params,
                "headers": headers,
                "timeout": timeout,
                "verify": verify,
            }
        )
        return FakeResponse()


def test_kithe_bridge_client_verifies_ssl_by_default(monkeypatch):
    monkeypatch.delenv("KITHE_BRIDGE_VERIFY_SSL", raising=False)
    session = FakeSession()
    client = KitheBridgeClient(
        base_url="https://example.test/api/kithe_bridge",
        token="secret",
        session=session,
    )

    client.fetch_page()

    assert session.calls[0]["verify"] is True


def test_kithe_bridge_client_can_disable_ssl_verification(monkeypatch):
    monkeypatch.setenv("KITHE_BRIDGE_VERIFY_SSL", "false")
    session = FakeSession()
    client = KitheBridgeClient(
        base_url="https://geomg.lib.umn.edu/api/kithe_bridge",
        token="secret",
        session=session,
    )

    client.fetch_page()

    assert session.calls[0]["verify"] is False
    assert session.calls[0]["url"] == "https://geomg.lib.umn.edu/api/kithe_bridge"
