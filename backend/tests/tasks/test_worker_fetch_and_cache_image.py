from unittest.mock import MagicMock, patch

import pytest

from app.services.thumbnail_capture import CaptureResult
from app.tasks.worker import (
    fetch_and_cache_image,
    generate_cog_thumbnail,
    generate_pmtiles_thumbnail,
)


@pytest.mark.parametrize(
    "task", [fetch_and_cache_image, generate_cog_thumbnail, generate_pmtiles_thumbnail]
)
def test_every_worker_uses_shared_capture_and_records_content_hash(task):
    with (
        patch(
            "app.services.thumbnail_capture.capture_thumbnail",
            return_value=CaptureResult("generated", "a" * 64),
        ) as capture,
        patch("app.tasks.worker.safe_record_thumbnail_state_sync") as state,
        patch("app.tasks.worker.release_thumbnail_queue_slot") as release,
    ):
        assert task("source", "map") is True
    assert capture.call_args.args == ("source", "map")
    assert state.call_args.args[0].source_hash == "a" * 64
    assert state.call_args.args[0].state == "success"
    release.assert_called_once_with("map", "source")


@pytest.mark.parametrize("result", [RuntimeError("storage failed"), CaptureResult("deferred")])
def test_worker_failure_and_deferral_never_record_success(result):
    from app.tasks.worker import _run_thumbnail_capture

    task = MagicMock()
    task.retry.side_effect = RuntimeError("retry scheduled")
    with (
        patch("app.services.thumbnail_capture.capture_thumbnail") as capture,
        patch("app.tasks.worker.safe_record_thumbnail_state_sync") as state,
        patch("app.tasks.worker.release_thumbnail_queue_slot") as release,
    ):
        if isinstance(result, Exception):
            capture.side_effect = result
        else:
            capture.return_value = result
        with pytest.raises(RuntimeError, match="retry scheduled"):
            _run_thumbnail_capture(task, "source", "map")
    assert state.call_args.args[0].state == "failure"
    release.assert_called_once()
