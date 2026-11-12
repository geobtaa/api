"""Library imports must not emit CLI diagnostics or configure file logging."""

import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "module_name",
    ["db.config", "db.migrations.add_enrichment_type", "app.gazetteer.import_all"],
)
def test_library_import_does_not_write_stdout_or_create_log_files(module_name, tmp_path):
    backend_root = Path(__file__).resolve().parents[1]
    env = dict(os.environ, PYTHONPATH=str(backend_root))
    result = subprocess.run(
        [sys.executable, "-c", f"import {module_name}"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )

    assert result.stdout == ""
    assert not (tmp_path / "gazetteer_import.log").exists()
