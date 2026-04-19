import pytest
from pathlib import Path
from git import Repo
from devwatcher.watchers.git import find_git_repos, GitPoller
from devwatcher.db import get_recent_events
from devwatcher.config import Config, CaptureConfig


@pytest.fixture
def git_repo(tmp_path):
    repo = Repo.init(tmp_path / "myrepo")
    repo.config_writer().set_value("user", "name", "Dev").release()
    repo.config_writer().set_value("user", "email", "dev@test.com").release()
    (tmp_path / "myrepo" / "README.md").write_text("hello", encoding="utf-8")
    repo.index.add(["README.md"])
    repo.index.commit("Initial commit")
    return repo


def test_find_git_repos_detects_subdirectory_repo(tmp_path, git_repo):
    repos = find_git_repos([tmp_path])
    paths = [str(r.working_dir) for r in repos]
    assert any(str(git_repo.working_dir) in p for p in paths)


def test_detects_new_commit(tmp_path, git_repo, tmp_db):
    config = Config(capture=CaptureConfig(watch_dirs=[str(tmp_path)]))
    poller = GitPoller([tmp_path], tmp_db, config)
    poller._init_states()

    (Path(git_repo.working_dir) / "file.py").write_text("x = 1", encoding="utf-8")
    git_repo.index.add(["file.py"])
    git_repo.index.commit("feat: add file")

    poller._poll()

    events = get_recent_events(tmp_db, limit=10)
    commit_events = [e for e in events if e["kind"] == "git_commit"]
    assert len(commit_events) == 1
    assert "feat: add file" in commit_events[0]["payload"]["message"]


def test_detects_branch_change(tmp_path, git_repo, tmp_db):
    config = Config(capture=CaptureConfig(watch_dirs=[str(tmp_path)]))
    poller = GitPoller([tmp_path], tmp_db, config)
    poller._init_states()

    git_repo.create_head("feature/new-branch")
    git_repo.heads["feature/new-branch"].checkout()

    poller._poll()

    events = get_recent_events(tmp_db, limit=10)
    branch_events = [e for e in events if e["kind"] == "git_branch"]
    assert len(branch_events) == 1
    assert branch_events[0]["payload"]["to"] == "feature/new-branch"


def test_does_not_duplicate_events_on_second_poll(tmp_path, git_repo, tmp_db):
    config = Config(capture=CaptureConfig(watch_dirs=[str(tmp_path)]))
    poller = GitPoller([tmp_path], tmp_db, config)
    poller._init_states()

    (Path(git_repo.working_dir) / "f.py").write_text("y=2", encoding="utf-8")
    git_repo.index.add(["f.py"])
    git_repo.index.commit("fix: patch")

    poller._poll()
    poller._poll()  # second poll, same commit

    events = get_recent_events(tmp_db, limit=10)
    commit_events = [e for e in events if e["kind"] == "git_commit"]
    assert len(commit_events) == 1
