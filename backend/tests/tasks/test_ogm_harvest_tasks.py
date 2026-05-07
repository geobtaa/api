from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.tasks import ogm_harvest


@pytest.mark.asyncio
async def test_ogm_harvest_all_nightly_trigger_selects_scheduled_modes(monkeypatch):
    monkeypatch.setattr(ogm_harvest.database, "is_connected", True)

    list_repos = AsyncMock(
        return_value=[
            {"ogm_repo_name": "nightly-repo", "ogm_enabled": True, "ogm_watch_mode": "nightly"},
            {"ogm_repo_name": "weekly-repo", "ogm_enabled": True, "ogm_watch_mode": "weekly"},
            {"ogm_repo_name": "scheduled-repo", "ogm_enabled": True, "ogm_watch_mode": "scheduled"},
            {"ogm_repo_name": "both-repo", "ogm_enabled": True, "ogm_watch_mode": "both"},
            {"ogm_repo_name": "manual-repo", "ogm_enabled": True, "ogm_watch_mode": "manual"},
            {"ogm_repo_name": "disabled-repo", "ogm_enabled": False, "ogm_watch_mode": "nightly"},
        ]
    )

    monkeypatch.setattr(
        ogm_harvest.OGMHarvestRepository,
        "list_repos",
        list_repos,
    )

    enqueued = []

    def fake_delay(*, repo_name: str, trigger: str):
        enqueued.append((repo_name, trigger))
        return SimpleNamespace(id=f"task-{repo_name}")

    monkeypatch.setattr(ogm_harvest.ogm_harvest_repo, "delay", fake_delay)

    result = await ogm_harvest._ogm_harvest_all_async(trigger="nightly")

    assert result["enqueued"] == 4
    assert result["repo_names"] == [
        "nightly-repo",
        "weekly-repo",
        "scheduled-repo",
        "both-repo",
    ]
    assert enqueued == [
        ("nightly-repo", "nightly"),
        ("weekly-repo", "nightly"),
        ("scheduled-repo", "nightly"),
        ("both-repo", "nightly"),
    ]
