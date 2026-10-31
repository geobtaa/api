from datetime import datetime, timezone

from app.services.preview_assets.metrics import summarize


def test_latest_attempt_summary_retains_stale_active_asset_age():
    result = summarize(
        [
            {
                "resource_id": "test",
                "active_manifest": {"generated_at": "2020-01-01T00:00:00Z"},
                "last_attempt": {
                    "status": "unavailable",
                    "metrics": {
                        "bytes_read": 123,
                        "seconds": 2.5,
                        "source_attempts": [
                            {
                                "url": "https://example.org/data?token=private",
                                "kind": "download",
                                "status": "unavailable",
                            }
                        ],
                    },
                },
            }
        ],
        now=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    assert result["stale_resource_ids"] == ["test"]
    assert result["provider_attempts"] == {"example.org | unavailable": 1}
    assert result["source_format_attempts"] == {"download | unavailable": 1}
    assert result["bytes_read"] == 123
    assert result["processing_seconds"] == 2.5
    assert "private" not in str(result)
