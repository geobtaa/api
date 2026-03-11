from unittest.mock import patch

from app.services import provider_throttle


def test_record_provider_failure_sets_cooldown_after_threshold():
    url = "https://gis.usgs.gov/thumb.png"

    with (
        patch.object(provider_throttle, "_failure_threshold", return_value=2),
        patch.object(provider_throttle, "_cooldown_seconds", return_value=600),
        patch.object(provider_throttle, "_slow_request_seconds", return_value=10.0),
        patch.object(provider_throttle._redis_client, "incr", side_effect=Exception("redis down")),
    ):
        provider_throttle._LOCAL_FAILURE_COUNTS.clear()
        provider_throttle._LOCAL_COOLDOWN_UNTIL.clear()

        first = provider_throttle.record_provider_failure(
            url,
            elapsed_seconds=30.0,
            failure_type="timeout",
        )
        second = provider_throttle.record_provider_failure(
            url,
            elapsed_seconds=30.0,
            failure_type="timeout",
        )

        assert first == 0.0
        assert second == 600
        assert provider_throttle.provider_origin_cooldown_remaining(url) > 0


def test_record_provider_success_clears_local_cooldown():
    url = "https://gis.usgs.gov/thumb.png"
    origin = provider_throttle.normalize_origin(url)
    assert origin is not None

    with patch.object(
        provider_throttle._redis_client, "delete", side_effect=Exception("redis down")
    ):
        provider_throttle._LOCAL_FAILURE_COUNTS[origin] = 5
        provider_throttle._LOCAL_COOLDOWN_UNTIL[origin] = 10**12

        provider_throttle.record_provider_success(url)

        assert provider_throttle.provider_origin_cooldown_remaining(url) == 0.0
