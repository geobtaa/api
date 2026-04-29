import io
from contextlib import nullcontext
from unittest.mock import MagicMock, patch

from PIL import Image

from app.tasks.worker import _remote_thumbnail_image_hash, fetch_and_cache_image


def _valid_png_bytes() -> bytes:
    img = Image.new("RGBA", (64, 64), color=(0, 128, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _large_jpeg_bytes() -> bytes:
    img = Image.new("RGB", (4500, 4300), color=(200, 180, 120))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    return buf.getvalue()


def _cached_image_write(mock_redis) -> tuple[str, bytes]:
    for call in mock_redis.set.call_args_list:
        key, value = call.args
        if isinstance(key, str) and key.startswith("image:"):
            return key, value

    for call in mock_redis.setex.call_args_list:
        key, _ttl, value = call.args
        if isinstance(key, str) and key.startswith("image:"):
            return key, value

    raise AssertionError("Expected thumbnail image bytes to be written to Redis")


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


def test_fetch_and_cache_image_resizes_large_remote_image_before_caching():
    source_url = "https://example.com/huge-thumb.jpg"
    response = MagicMock()
    response.status_code = 200
    response.content = _large_jpeg_bytes()
    response.headers = {"Content-Type": "image/jpeg"}
    response.raise_for_status = MagicMock()

    with (
        patch("app.tasks.worker._resolve_image_url", return_value=source_url),
        patch("app.tasks.worker.redis_client") as mock_redis,
        patch("app.tasks.worker.requests.get", return_value=response),
        patch(
            "app.tasks.worker.provider_request_slot",
            side_effect=lambda *args, **kwargs: nullcontext(MagicMock(waited_seconds=0.0)),
        ),
        patch("app.tasks.worker.safe_record_thumbnail_state_sync"),
        patch("app.tasks.worker.release_thumbnail_queue_slot"),
    ):
        mock_redis.exists.return_value = False

        result = fetch_and_cache_image(source_url, "resource-large")

        assert result is True
        image_key, cached_bytes = _cached_image_write(mock_redis)
        assert image_key == f"image:{_remote_thumbnail_image_hash(source_url)}"
        cached_image = Image.open(io.BytesIO(cached_bytes))
        assert max(cached_image.size) <= 512
        assert cached_image.format == "JPEG"
        assert len(cached_bytes) < len(response.content)
