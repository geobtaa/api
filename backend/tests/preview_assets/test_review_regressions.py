"""Behavioral regressions discovered during the full shared-preview PR review."""

import json
import sys
import time

import pytest

from app.services.preview_assets.io import Budget
from app.services.preview_assets.models import Limits, Outcome, PreviewError
from app.services.preview_assets.presentation import public_preview
from app.services.preview_assets.process import run_tool
from app.services.preview_assets.repository import record_signature


def test_public_viewer_contract_does_not_scale_with_private_tile_registry():
    manifest = {
        "version": "1",
        "status": "ready",
        "source_fingerprint": "source",
        "layers": [{"id": "iiif", "format": "iiif", "url": "/info.json", "asset_key": "private"}],
        "iiif_assets": {f"image/{n}.jpg": "a" * 64 + ".jpg" for n in range(10000)},
        "metrics": {"review_thumbnail_key": "private", "coverage_error": "worker diagnostic"},
        "dependencies": [{"resource_id": "child", "signature": "internal"}],
        "coverage_key": "private",
    }
    payload = public_preview(manifest)
    assert len(json.dumps(payload)) < 500
    assert payload["layers"] == [{"id": "iiif", "format": "iiif", "url": "/info.json"}]
    assert payload["source_fingerprint"] == "source"
    assert len(manifest["iiif_assets"]) == 10000
    assert not {"iiif_assets", "metrics", "dependencies", "coverage_key"} & payload.keys()


@pytest.mark.parametrize("field", ["gbl_wxsIdentifier_s", "dct_title_s"])
def test_service_layer_and_index_title_changes_invalidate_publication(field):
    original = {"dct_references_s": "{}", field: "before"}
    assert record_signature(original) != record_signature({**original, field: "after"})
    assert record_signature(original) == record_signature(
        {k.lower(): v for k, v in original.items()}
    )


def test_failed_tool_cannot_load_an_unbounded_error_log(tmp_path, monkeypatch):
    monkeypatch.delenv("PREVIEW_CHILD_JOB", raising=False)
    with pytest.raises(PreviewError) as failure:
        run_tool(
            [sys.executable, "-c", "import sys; sys.stdout.write('x' * (9 << 20)); sys.exit(1)"],
            Budget(Limits(), tmp_path),
        )
    assert failure.value.status == Outcome.OVER_LIMIT
    assert "Tool output" in str(failure.value)


def test_failed_launcher_does_not_leave_descendants_running(tmp_path, monkeypatch):
    monkeypatch.delenv("PREVIEW_CHILD_JOB", raising=False)
    marker = tmp_path / "orphan-survived"
    child = f"import time,pathlib; time.sleep(2); pathlib.Path({str(marker)!r}).write_text('bad')"
    launcher = (
        f'import subprocess,sys; subprocess.Popen([sys.executable,"-c",{child!r}]); sys.exit(1)'
    )
    with pytest.raises(PreviewError):
        run_tool([sys.executable, "-c", launcher], Budget(Limits(), tmp_path))
    time.sleep(2.2)
    assert not marker.exists()
