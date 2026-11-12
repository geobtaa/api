import os
import subprocess
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK = REPO_ROOT / ".kamal/hooks/post-deploy"
DEPLOYED_SHA = "a" * 40


@pytest.fixture
def hook_env(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, content in {
        "git": 'printf "%s\\n" "$@" > "$GIT_ARGS"\nprintf "%s\\n" "$RESOLVED_SHA"\n',
        "gh": 'printf "%s\\n" "$@" > "$GH_ARGS"\nexit "${GH_EXIT:-0}"\n',
    }.items():
        path = bin_dir / name
        path.write_text("#!/bin/sh\n" + content)
        path.chmod(0o755)
    return {
        "PATH": str(bin_dir),
        "KAMAL_DESTINATION": "prd",
        "KAMAL_VERSION": "deployed-tag",
        "RESOLVED_SHA": DEPLOYED_SHA,
        "GIT_ARGS": str(tmp_path / "git-args"),
        "GH_ARGS": str(tmp_path / "gh-args"),
    }


def _run_hook(env):
    return subprocess.run(["/bin/sh", str(HOOK)], env=env, capture_output=True, text=True)


@pytest.mark.parametrize("command", ["deploy", "redeploy", "rollback"])
def test_production_hook_dispatches_deployed_commit(hook_env, command):
    hook_env["KAMAL_COMMAND"] = command
    result = _run_hook(hook_env)
    assert result.returncode == 0, result.stderr
    assert Path(hook_env["GIT_ARGS"]).read_text().splitlines() == [
        "rev-parse",
        "--verify",
        "deployed-tag^{commit}",
    ]
    assert Path(hook_env["GH_ARGS"]).read_text().splitlines() == [
        "workflow",
        "run",
        "production-pages-smoke.yml",
        "--repo",
        "geobtaa/api",
        "--ref",
        "main",
        "--raw-field",
        f"deployed_sha={DEPLOYED_SHA}",
    ]
    assert os.access(HOOK, os.X_OK)


@pytest.mark.parametrize("destination", ["", "dev1", "dev2"])
def test_nonproduction_hook_does_not_dispatch(hook_env, destination):
    hook_env["KAMAL_DESTINATION"] = destination
    result = _run_hook(hook_env)
    assert result.returncode == 0
    assert not Path(hook_env["GH_ARGS"]).exists()
    assert not Path(hook_env["GIT_ARGS"]).exists()


def test_dispatch_failure_is_explicit_about_completed_deployment(hook_env):
    hook_env["GH_EXIT"] = "1"
    result = _run_hook(hook_env)
    assert result.returncode == 1
    assert "Deployment completed" in result.stderr
    assert "smoke tests were not queued" in result.stderr


def test_missing_cli_is_reported(hook_env):
    (Path(hook_env["PATH"]) / "gh").unlink()
    result = _run_hook(hook_env)
    assert result.returncode == 1
    assert "GitHub CLI (gh) is required" in result.stderr


@pytest.mark.parametrize("version", ["", "--help"])
def test_invalid_version_is_not_dispatched(hook_env, version):
    hook_env["KAMAL_VERSION"] = version
    result = _run_hook(hook_env)
    assert result.returncode == 1
    assert not Path(hook_env["GH_ARGS"]).exists()


def test_smoke_workflow_uses_dispatch_and_deployed_revision():
    workflow = yaml.load(
        (REPO_ROOT / ".github/workflows/production-pages-smoke.yml").read_text(),
        Loader=yaml.BaseLoader,
    )
    assert set(workflow["on"]) == {"workflow_dispatch"}
    assert "deployed_sha" in workflow["on"]["workflow_dispatch"]["inputs"]
    checkout = workflow["jobs"]["production-pages-smoke"]["steps"][0]
    assert checkout["with"]["ref"] == "${{ inputs.deployed_sha || github.sha }}"
