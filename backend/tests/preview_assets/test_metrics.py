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


def test_status_cli_emits_only_json(tmp_path):
    import json
    import os
    import subprocess
    import sys
    from pathlib import Path

    backend = Path(__file__).resolve().parents[2]
    report = tmp_path / "report.json"
    report.write_text("[]")
    result = subprocess.run(
        [
            sys.executable,
            str(backend / "scripts/preview_assets_status.py"),
            "--report",
            str(report),
        ],
        cwd=backend,
        env={**os.environ, "PYTHONPATH": str(backend)},
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    assert json.loads(result.stdout)["records"] == 0
