import io
from contextlib import nullcontext
from unittest.mock import MagicMock, patch

from PIL import Image

from app.tasks.worker import fetch_and_cache_image


def _valid_png_bytes() -> bytes:
    img = Image.new("RGBA", (64, 64), color=(0, 128, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_fetch_and_cache_image_records_success_and_uses_provider_throttle():
    source_url = "https://example.com/thumb.png"
    response = MagicMock()
    response.status_code = 200
    response.content = _valid_png_bytes()
    response.headers = {"Content-Type": "image/png"}
    response.raise_for_status = MagicMock()

    with (
        patch("app.tasks.worker._resolve_image_url", return_value=source_url),
        patch("app.tasks.worker.redis_client") as mock_redis,
        patch("app.tasks.worker.requests.get", return_value=response),
        patch(
            "app.tasks.worker.provider_request_slot",
            side_effect=lambda *args, **kwargs: nullcontext(MagicMock(waited_seconds=0.0)),
        ) as mock_provider_slot,
        patch("app.tasks.worker.safe_record_thumbnail_state_sync") as mock_state,
        patch("app.tasks.worker.release_thumbnail_queue_slot"),
    ):
        mock_redis.exists.return_value = False

        result = fetch_and_cache_image(source_url, "resource-1")

        assert result is True
        mock_provider_slot.assert_called_once()
        payload = mock_state.call_args.args[0]
        assert payload.state == "success"
        assert payload.source_type == "remote"
        assert payload.resource_id == "resource-1"


def test_fetch_and_cache_image_records_failure_for_invalid_content():
    source_url = "https://example.com/thumb.png"
    response = MagicMock()
    response.status_code = 200
    response.content = b"<html>not an image</html>"
    response.headers = {"Content-Type": "text/html"}
    response.raise_for_status = MagicMock()

    with (
        patch("app.tasks.worker._resolve_image_url", return_value=source_url),
        patch("app.tasks.worker.redis_client") as mock_redis,
        patch("app.tasks.worker.requests.get", return_value=response),
        patch(
            "app.tasks.worker.provider_request_slot",
            side_effect=lambda *args, **kwargs: nullcontext(MagicMock(waited_seconds=0.0)),
        ),
        patch("app.tasks.worker.safe_record_thumbnail_state_sync") as mock_state,
        patch("app.tasks.worker.release_thumbnail_queue_slot"),
    ):
        mock_redis.exists.return_value = False

        result = fetch_and_cache_image(source_url, "resource-2")

        assert result is False
        payload = mock_state.call_args.args[0]
        assert payload.state == "failure"
        assert payload.source_type == "remote"
        assert payload.resource_id == "resource-2"
