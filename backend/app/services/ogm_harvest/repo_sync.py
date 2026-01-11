from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import shutil


@dataclass(frozen=True)
class RepoSyncResult:
    repo_name: str
    repo_dir: Path
    head_sha: Optional[str]
    action: str  # clone|pull|noop


class OGMRepoSync:
    """Clone/pull OpenGeoMetadata GitHub repos into a local checkout directory."""

    def __init__(
        self,
        base_dir: str | Path | None = None,
        org: str = "OpenGeoMetadata",
    ):
        self.base_dir = Path(base_dir or os.getenv("OGM_CHECKOUT_PATH", "data/opengeometadata"))
        self.org = org

    def ensure_repo(self, repo_name: str) -> RepoSyncResult:
        """Clone if missing; otherwise pull."""
        if shutil.which("git") is None:
            raise FileNotFoundError(
                "git is required to harvest OpenGeoMetadata repos, but was not found in PATH. "
                "Install git in the API/Celery container image."
            )
        self.base_dir.mkdir(parents=True, exist_ok=True)
        repo_dir = self.base_dir / repo_name
        if not repo_dir.exists():
            return self._clone(repo_name, repo_dir)
        return self._pull(repo_name, repo_dir)

    def _clone(self, repo_name: str, repo_dir: Path) -> RepoSyncResult:
        repo_url = f"https://github.com/{self.org}/{repo_name}.git"
        subprocess.run(
            ["git", "clone", "--depth", "1", repo_url, str(repo_dir)],
            check=True,
            capture_output=True,
            text=True,
        )
        head_sha = self._head_sha(repo_dir)
        return RepoSyncResult(repo_name=repo_name, repo_dir=repo_dir, head_sha=head_sha, action="clone")

    def _pull(self, repo_name: str, repo_dir: Path) -> RepoSyncResult:
        subprocess.run(
            ["git", "-C", str(repo_dir), "pull", "--ff-only"],
            check=True,
            capture_output=True,
            text=True,
        )
        head_sha = self._head_sha(repo_dir)
        return RepoSyncResult(repo_name=repo_name, repo_dir=repo_dir, head_sha=head_sha, action="pull")

    def _head_sha(self, repo_dir: Path) -> Optional[str]:
        try:
            out = subprocess.run(
                ["git", "-C", str(repo_dir), "rev-parse", "HEAD"],
                check=True,
                capture_output=True,
                text=True,
            )
            sha = (out.stdout or "").strip()
            return sha or None
        except Exception:
            return None

