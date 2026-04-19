import pytest
from pathlib import Path
from git import Repo
from devwatcher.watchers.git import find_git_repos, GitPoller, _parse_branch_info
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


# --- find_git_repos ---

def test_find_git_repos_detects_subdirectory_repo(tmp_path, git_repo):
    repos = find_git_repos([tmp_path])
    paths = [str(r.working_dir) for r in repos]
    assert any(str(git_repo.working_dir) in p for p in paths)


# --- _parse_branch_info ---

def test_parse_branch_info_extracts_azure_work_item():
    assert _parse_branch_info("task/AB#1234-my-feature") == {
        "work_item_id": "1234",
        "work_item_ref": "AB#1234",
    }


def test_parse_branch_info_handles_users_prefix():
    info = _parse_branch_info("users/dev/AB#5678-fix-bug")
    assert info["work_item_id"] == "5678"
    assert info["work_item_ref"] == "AB#5678"


def test_parse_branch_info_returns_empty_for_plain_branch():
    assert _parse_branch_info("feature/my-feature") == {}
    assert _parse_branch_info("main") == {}


# --- GitPoller ---

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
    payload = commit_events[0]["payload"]
    assert "feat: add file" in payload["message"]
    assert "stats" in payload
    assert payload["stats"]["files"] >= 1


def test_commit_payload_includes_branch_and_work_item(tmp_path, git_repo, tmp_db):
    config = Config(capture=CaptureConfig(watch_dirs=[str(tmp_path)]))
    poller = GitPoller([tmp_path], tmp_db, config)

    git_repo.create_head("task/AB#42-new-feature")
    git_repo.heads["task/AB#42-new-feature"].checkout()
    poller._init_states()

    (Path(git_repo.working_dir) / "feat.py").write_text("pass", encoding="utf-8")
    git_repo.index.add(["feat.py"])
    git_repo.index.commit("feat: implement feature")

    poller._poll()

    events = get_recent_events(tmp_db, limit=10)
    commit_events = [e for e in events if e["kind"] == "git_commit"]
    assert len(commit_events) == 1
    payload = commit_events[0]["payload"]
    assert payload["branch"] == "task/AB#42-new-feature"
    assert payload["work_item_ref"] == "AB#42"
    assert payload["work_item_id"] == "42"


def test_commit_includes_diff_when_git_diffs_enabled(tmp_path, git_repo, tmp_db):
    config = Config(capture=CaptureConfig(watch_dirs=[str(tmp_path)], git_diffs=True))
    poller = GitPoller([tmp_path], tmp_db, config)
    poller._init_states()

    (Path(git_repo.working_dir) / "code.py").write_text("def foo(): pass", encoding="utf-8")
    git_repo.index.add(["code.py"])
    git_repo.index.commit("feat: add foo")

    poller._poll()

    events = get_recent_events(tmp_db, limit=10)
    commit_events = [e for e in events if e["kind"] == "git_commit"]
    assert len(commit_events) == 1
    assert "diff" in commit_events[0]["payload"]


def test_commit_excludes_diff_when_git_diffs_disabled(tmp_path, git_repo, tmp_db):
    config = Config(capture=CaptureConfig(watch_dirs=[str(tmp_path)], git_diffs=False))
    poller = GitPoller([tmp_path], tmp_db, config)
    poller._init_states()

    (Path(git_repo.working_dir) / "code.py").write_text("def bar(): pass", encoding="utf-8")
    git_repo.index.add(["code.py"])
    git_repo.index.commit("feat: add bar")

    poller._poll()

    events = get_recent_events(tmp_db, limit=10)
    commit_events = [e for e in events if e["kind"] == "git_commit"]
    assert "diff" not in commit_events[0]["payload"]


def test_detects_branch_change(tmp_path, git_repo, tmp_db):
    config = Config(capture=CaptureConfig(watch_dirs=[str(tmp_path)]))
    poller = GitPoller([tmp_path], tmp_db, config)
    poller._init_states()

    git_repo.create_head("task/AB#99-new")
    git_repo.heads["task/AB#99-new"].checkout()

    poller._poll()

    events = get_recent_events(tmp_db, limit=10)
    branch_events = [e for e in events if e["kind"] == "git_branch"]
    assert len(branch_events) == 1
    payload = branch_events[0]["payload"]
    assert payload["to"] == "task/AB#99-new"
    assert payload["work_item_ref"] == "AB#99"


def test_does_not_duplicate_events_on_second_poll(tmp_path, git_repo, tmp_db):
    config = Config(capture=CaptureConfig(watch_dirs=[str(tmp_path)]))
    poller = GitPoller([tmp_path], tmp_db, config)
    poller._init_states()

    (Path(git_repo.working_dir) / "f.py").write_text("y=2", encoding="utf-8")
    git_repo.index.add(["f.py"])
    git_repo.index.commit("fix: patch")

    poller._poll()
    poller._poll()

    events = get_recent_events(tmp_db, limit=10)
    commit_events = [e for e in events if e["kind"] == "git_commit"]
    assert len(commit_events) == 1
