import json
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.api.v1.endpoint_modules.admin import (
    TriggerBridgeSyncRequest,
    bridge_sync_status,
    get_bridge_sync_run,
    list_bridge_missing,
    list_bridge_sync_runs,
    trigger_bridge_sync,
)


@pytest.mark.asyncio
@patch("app.api.v1.endpoint_modules.admin.bridge_sync_all")
async def test_trigger_bridge_sync_enqueues_task(mock_task):
    mock_task.delay.return_value = Mock(id="bridge-task-123")

    response = await trigger_bridge_sync(
        TriggerBridgeSyncRequest(bridge_trigger="manual", limit=25)
    )

    payload = json.loads(response.body)
    assert payload["queued"] == "kithe_bridge"
    assert payload["task_id"] == "bridge-task-123"
    assert payload["limit"] == 25
    mock_task.delay.assert_called_once_with(trigger="manual", limit=25)


@pytest.mark.asyncio
@patch("app.api.v1.endpoint_modules.admin.bridge_sync_all")
async def test_trigger_bridge_sync_enqueues_task_with_changed_since(mock_task):
    mock_task.delay.return_value = Mock(id="bridge-task-456")

    cutoff = "2025-08-01T00:00:00Z"
    response = await trigger_bridge_sync(
        TriggerBridgeSyncRequest(bridge_trigger="manual", limit=25, changed_since=cutoff)
    )

    payload = json.loads(response.body)
    assert payload["queued"] == "kithe_bridge"
    assert payload["task_id"] == "bridge-task-456"
    assert payload["limit"] == 25
    assert payload["changed_since"] == cutoff
    mock_task.delay.assert_called_once_with(trigger="manual", limit=25, changed_since=cutoff)


@pytest.mark.asyncio
@patch("app.api.v1.endpoint_modules.admin.bridge_repo")
async def test_list_bridge_sync_runs_returns_runs(mock_repo):
    mock_repo.list_sync_runs = AsyncMock(
        return_value=[{"bridge_id": 12, "bridge_status": "running"}]
    )

    response = await list_bridge_sync_runs(status="running", limit=10, offset=0)

    payload = json.loads(response.body)
    assert payload["runs"] == [{"bridge_id": 12, "bridge_status": "running"}]
    mock_repo.list_sync_runs.assert_awaited_once_with(bridge_status="running", limit=10, offset=0)


@pytest.mark.asyncio
@patch("app.api.v1.endpoint_modules.admin.bridge_repo")
async def test_get_bridge_sync_run_returns_detail(mock_repo):
    mock_repo.get_sync_run = AsyncMock(return_value={"bridge_id": 7, "bridge_status": "success"})

    response = await get_bridge_sync_run(7)

    payload = json.loads(response.body)
    assert payload["run"] == {"bridge_id": 7, "bridge_status": "success"}
    mock_repo.get_sync_run.assert_awaited_once_with(7)


@pytest.mark.asyncio
@patch("app.api.v1.endpoint_modules.admin.bridge_repo")
async def test_bridge_sync_status_returns_summary(mock_repo):
    mock_repo.list_status_counts = AsyncMock(
        return_value={"counts_last_runs": {"success": 1}, "running_runs": []}
    )

    response = await bridge_sync_status(include_celery=False, runs_limit=50)

    payload = json.loads(response.body)
    assert payload["counts_last_runs"] == {"success": 1}
    mock_repo.list_status_counts.assert_awaited_once_with(runs_limit=50)


@pytest.mark.asyncio
@patch("app.api.v1.endpoint_modules.admin.bridge_repo")
async def test_list_bridge_missing_returns_missing_rows(mock_repo):
    mock_repo.list_missing = AsyncMock(
        return_value=[{"bridge_resource_id": "missing-1", "bridge_status": "retired"}]
    )

    response = await list_bridge_missing(limit=20, offset=5)

    payload = json.loads(response.body)
    assert payload["missing"] == [{"bridge_resource_id": "missing-1", "bridge_status": "retired"}]
    mock_repo.list_missing.assert_awaited_once_with(limit=20, offset=5)
