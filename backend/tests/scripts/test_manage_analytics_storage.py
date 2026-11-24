"""The management command must preserve the original reporting failure."""

from unittest.mock import MagicMock

import pytest

from app.services.analytics_reporting import pipeline, storage
from db.migrations import analytics_storage
from scripts import manage_analytics_storage as command


@pytest.mark.parametrize("health_connection_fails", [False, True])
def test_publication_failure_survives_unavailable_health_store(
    monkeypatch, health_connection_fails
):
    engine = MagicMock()
    failure = RuntimeError("Reporting schema is missing; run analytics storage ensure first")
    monkeypatch.setattr(command.sys, "argv", ["manage_analytics_storage.py", "--mode", "reporting"])
    monkeypatch.setattr(command, "load_dotenv", lambda: None)
    monkeypatch.setattr(analytics_storage, "analytics_storage_engine", lambda: engine)
    monkeypatch.setattr(pipeline, "run", MagicMock(side_effect=failure))
    monkeypatch.setattr(
        storage, "health", MagicMock(side_effect=RuntimeError("health table missing"))
    )
    if health_connection_fails:
        engine.begin.side_effect = RuntimeError("database unavailable")
    with pytest.raises(RuntimeError) as caught:
        command.main()
    assert caught.value is failure
    engine.dispose.assert_called_once()
