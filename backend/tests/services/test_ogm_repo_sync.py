import subprocess

from app.services.ogm_harvest.repo_sync import OGMRepoSync, RepoSyncResult


def test_ensure_repo_reclones_when_directory_is_not_git_repo(tmp_path, monkeypatch):
    repo_name = "edu.utexas"
    repo_dir = tmp_path / repo_name
    repo_dir.mkdir(parents=True)
    (repo_dir / "not_git.txt").write_text("broken checkout", encoding="utf-8")

    def fake_clone(self, _repo_name, _repo_dir, _git_executable):
        _repo_dir.mkdir(parents=True, exist_ok=True)
        (_repo_dir / ".git").mkdir(parents=True, exist_ok=True)
        return RepoSyncResult(_repo_name, _repo_dir, "reclone-sha", "clone")

    monkeypatch.setattr(
        "app.services.ogm_harvest.repo_sync.shutil.which", lambda _name: "/usr/bin/git"
    )
    monkeypatch.setattr(OGMRepoSync, "_clone", fake_clone)

    sync = OGMRepoSync(base_dir=tmp_path)
    result = sync.ensure_repo(repo_name)

    assert result.action == "reclone"
    assert result.head_sha == "reclone-sha"
    assert (repo_dir / ".git").exists()


def test_pull_reclones_when_ff_only_pull_fails(tmp_path, monkeypatch):
    repo_name = "edu.utexas"
    repo_dir = tmp_path / repo_name
    repo_dir.mkdir(parents=True)
    (repo_dir / ".git").mkdir(parents=True)

    calls = []

    def fake_run(cmd, check, capture_output, text):
        calls.append(cmd)
        if cmd[:4] == ["/usr/bin/git", "-C", str(repo_dir), "pull"]:
            raise subprocess.CalledProcessError(returncode=1, cmd=cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    def fake_clone(self, _repo_name, _repo_dir, _git_executable):
        _repo_dir.mkdir(parents=True, exist_ok=True)
        (_repo_dir / ".git").mkdir(parents=True, exist_ok=True)
        return RepoSyncResult(_repo_name, _repo_dir, "new-sha", "clone")

    monkeypatch.setattr(
        "app.services.ogm_harvest.repo_sync.shutil.which", lambda _name: "/usr/bin/git"
    )
    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(OGMRepoSync, "_clone", fake_clone)

    sync = OGMRepoSync(base_dir=tmp_path)
    result = sync.ensure_repo(repo_name)

    assert result.action == "reclone"
    assert result.head_sha == "new-sha"
    assert any(cmd[:4] == ["/usr/bin/git", "-C", str(repo_dir), "pull"] for cmd in calls)
