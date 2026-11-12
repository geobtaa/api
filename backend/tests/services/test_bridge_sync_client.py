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


def test_bridge_client_rejects_nonpositive_retry_limits(monkeypatch):
    import pytest

    from app.services.bridge_sync import client as client_module

    for retry_limit in (0, -1):
        monkeypatch.setattr(client_module, "BRIDGE_FETCH_MAX_RETRIES", retry_limit)
        session = FakeSession()
        client = KitheBridgeClient(
            base_url="https://example.test/bridge", token="test-token", session=session
        )

        with pytest.raises(ValueError, match="must be greater than zero"):
            client.fetch_page()
        assert session.calls == []


def test_bridge_client_retries_transient_failures_then_returns_response(monkeypatch):
    from unittest.mock import Mock

    import requests

    from app.services.bridge_sync import client as client_module

    monkeypatch.setattr(client_module, "BRIDGE_FETCH_MAX_RETRIES", 3)
    monkeypatch.setattr(client_module, "BRIDGE_FETCH_RETRY_BACKOFF_SECONDS", 2)
    sleep = Mock()
    monkeypatch.setattr(client_module.time, "sleep", sleep)
    session = Mock()
    session.get.side_effect = [requests.ConnectionError("temporary"), FakeResponse()]
    client = KitheBridgeClient(
        base_url="https://example.test/bridge", token="test-token", session=session
    )

    assert client.fetch_page().data == []
    assert session.get.call_count == 2
    sleep.assert_called_once_with(2)


def test_bridge_client_preserves_last_error_when_retries_are_exhausted(monkeypatch):
    from unittest.mock import Mock

    import pytest
    import requests

    from app.services.bridge_sync import client as client_module

    monkeypatch.setattr(client_module, "BRIDGE_FETCH_MAX_RETRIES", 2)
    monkeypatch.setattr(client_module.time, "sleep", Mock())
    error = requests.Timeout("request timed out")
    session = Mock()
    session.get.side_effect = error
    client = KitheBridgeClient(
        base_url="https://example.test/bridge", token="test-token", session=session
    )

    with pytest.raises(requests.Timeout) as caught:
        client.fetch_page()
    assert caught.value is error
    assert session.get.call_count == 2
