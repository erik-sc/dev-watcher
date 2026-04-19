"""
End-to-end integration tests — real components, no mocked observers or DB calls.

Covers all 4 event types:
  file_save         — real watchdog Observer watching a temp dir
  git_commit        — real git repo, GitPoller._poll()
  git_branch        — real git repo branch switch, GitPoller._poll()
  window_focus      — mocked win32gui (no real GUI possible in CI)
"""
from __future__ import annotations
import sys
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from git import Repo

from devwatcher.config import Config, CaptureConfig, PrivacyConfig
from devwatcher.db import get_recent_events
from devwatcher.watchers.files import FileWatcher
from devwatcher.watchers.git import GitPoller
from devwatcher.watchers.window import WindowMonitor


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _wait_for(tmp_db, kind: str, timeout: float = 5.0) -> list[dict]:
    """Poll DB until at least one event of `kind` appears or timeout expires."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        matching = [e for e in get_recent_events(tmp_db, limit=50) if e["kind"] == kind]
        if matching:
            return matching
        time.sleep(0.1)
    return []


@pytest.fixture
def git_repo(tmp_path):
    repo = Repo.init(tmp_path / "repo")
    repo.config_writer().set_value("user", "name", "Dev").release()
    repo.config_writer().set_value("user", "email", "dev@test.com").release()
    (tmp_path / "repo" / "README.md").write_text("init", encoding="utf-8")
    repo.index.add(["README.md"])
    repo.index.commit("init")
    return repo


# ---------------------------------------------------------------------------
# file_save — real watchdog Observer
# ---------------------------------------------------------------------------

class TestFileSaveE2E:
    def test_file_modification_produces_file_save_event(self, tmp_db, tmp_path):
        config = Config(
            capture=CaptureConfig(watch_dirs=[str(tmp_path)]),
            privacy=PrivacyConfig(global_ignore=[]),
        )
        watcher = FileWatcher([tmp_path], tmp_db, config)
        t = threading.Thread(target=watcher.start, daemon=True)
        t.start()
        time.sleep(0.4)  # let Observer initialise

        target = tmp_path / "app.py"
        target.write_text("x = 1", encoding="utf-8")
        time.sleep(0.05)
        target.write_text("x = 2", encoding="utf-8")  # guaranteed on_modified

        events = _wait_for(tmp_db, "file_save")
        watcher.stop()

        assert events, "No file_save event recorded"
        assert any("app.py" in e["payload"]["path"] for e in events)

    def test_nested_file_modification_detected(self, tmp_db, tmp_path):
        subdir = tmp_path / "src" / "utils"
        subdir.mkdir(parents=True)
        config = Config(
            capture=CaptureConfig(watch_dirs=[str(tmp_path)]),
            privacy=PrivacyConfig(global_ignore=[]),
        )
        watcher = FileWatcher([tmp_path], tmp_db, config)
        t = threading.Thread(target=watcher.start, daemon=True)
        t.start()
        time.sleep(0.4)

        f = subdir / "helpers.py"
        f.write_text("def foo(): pass", encoding="utf-8")
        time.sleep(0.05)
        f.write_text("def foo(): return 1", encoding="utf-8")

        events = _wait_for(tmp_db, "file_save")
        watcher.stop()

        assert events
        assert any("helpers.py" in e["payload"]["path"] for e in events)

    def test_ignored_directory_produces_no_event(self, tmp_db, tmp_path):
        secret_dir = tmp_path / "secret_dir"
        secret_dir.mkdir()
        config = Config(
            capture=CaptureConfig(watch_dirs=[str(tmp_path)]),
            privacy=PrivacyConfig(global_ignore=["secret_dir*"]),
        )
        watcher = FileWatcher([tmp_path], tmp_db, config)
        t = threading.Thread(target=watcher.start, daemon=True)
        t.start()
        time.sleep(0.4)

        f = secret_dir / "credentials.txt"
        f.write_text("token=abc123", encoding="utf-8")
        time.sleep(0.05)
        f.write_text("token=xyz789", encoding="utf-8")

        time.sleep(1.5)  # wait out any delayed events
        watcher.stop()

        events = get_recent_events(tmp_db, limit=50)
        assert not any("secret_dir" in str(e.get("payload", "")) for e in events)


# ---------------------------------------------------------------------------
# git_commit + git_branch — real git repo via GitPoller._poll()
# ---------------------------------------------------------------------------

class TestGitPollerE2E:
    def test_new_commit_produces_git_commit_event(self, tmp_db, tmp_path, git_repo):
        config = Config(capture=CaptureConfig(watch_dirs=[str(tmp_path)]))
        poller = GitPoller([tmp_path], tmp_db, config)
        poller._init_states()

        (Path(git_repo.working_dir) / "main.py").write_text("print('hi')", encoding="utf-8")
        git_repo.index.add(["main.py"])
        git_repo.index.commit("feat: add main")

        poller._poll()

        events = get_recent_events(tmp_db, limit=10)
        commit_events = [e for e in events if e["kind"] == "git_commit"]
        assert commit_events, "No git_commit event recorded"
        assert "feat: add main" in commit_events[0]["payload"]["message"]
        assert "main.py" in commit_events[0]["payload"]["files"]

    def test_branch_switch_produces_git_branch_event(self, tmp_db, tmp_path, git_repo):
        config = Config(capture=CaptureConfig(watch_dirs=[str(tmp_path)]))
        poller = GitPoller([tmp_path], tmp_db, config)
        poller._init_states()

        git_repo.create_head("feature/auth")
        git_repo.heads["feature/auth"].checkout()

        poller._poll()

        events = get_recent_events(tmp_db, limit=10)
        branch_events = [e for e in events if e["kind"] == "git_branch"]
        assert branch_events, "No git_branch event recorded"
        assert branch_events[0]["payload"]["to"] == "feature/auth"

    def test_commit_branch_commit_sequence(self, tmp_db, tmp_path, git_repo):
        """Commit → switch branch → commit: produces 2 git_commit + 1 git_branch in order."""
        config = Config(capture=CaptureConfig(watch_dirs=[str(tmp_path)]))
        poller = GitPoller([tmp_path], tmp_db, config)
        poller._init_states()

        # First commit on master/main
        (Path(git_repo.working_dir) / "v1.py").write_text("v=1", encoding="utf-8")
        git_repo.index.add(["v1.py"])
        git_repo.index.commit("feat: v1")
        poller._poll()

        # Switch branch
        git_repo.create_head("release/1.0")
        git_repo.heads["release/1.0"].checkout()
        poller._poll()

        # Second commit on new branch
        (Path(git_repo.working_dir) / "v2.py").write_text("v=2", encoding="utf-8")
        git_repo.index.add(["v2.py"])
        git_repo.index.commit("feat: v2")
        poller._poll()

        events = get_recent_events(tmp_db, limit=20)
        kinds = [e["kind"] for e in events]
        assert kinds.count("git_commit") == 2
        assert kinds.count("git_branch") == 1
        messages = [e["payload"]["message"] for e in events if e["kind"] == "git_commit"]
        assert "feat: v1" in messages
        assert "feat: v2" in messages

    def test_no_duplicate_events_on_repeated_poll(self, tmp_db, tmp_path, git_repo):
        config = Config(capture=CaptureConfig(watch_dirs=[str(tmp_path)]))
        poller = GitPoller([tmp_path], tmp_db, config)
        poller._init_states()

        (Path(git_repo.working_dir) / "once.py").write_text("x=1", encoding="utf-8")
        git_repo.index.add(["once.py"])
        git_repo.index.commit("single commit")

        poller._poll()
        poller._poll()
        poller._poll()

        events = get_recent_events(tmp_db, limit=10)
        assert sum(1 for e in events if e["kind"] == "git_commit") == 1


# ---------------------------------------------------------------------------
# window_focus — mocked win32gui (real GUI not testable in CI)
# ---------------------------------------------------------------------------

class TestWindowFocusE2E:
    def _run_one_cycle(self, monitor, win32gui_mock):
        def stop_on_sleep(_n):
            monitor.stop()
        with patch.dict(sys.modules, {"win32gui": win32gui_mock}), \
             patch("devwatcher.watchers.window.time.sleep", side_effect=stop_on_sleep):
            monitor.start()

    def test_title_change_produces_window_focus_event(self, tmp_db):
        mock_win32gui = MagicMock()
        mock_win32gui.GetForegroundWindow.return_value = 1
        mock_win32gui.GetWindowText.return_value = "devwatcher — VS Code"

        monitor = WindowMonitor(tmp_db, MagicMock())
        self._run_one_cycle(monitor, mock_win32gui)

        events = get_recent_events(tmp_db, limit=10)
        window_events = [e for e in events if e["kind"] == "window_focus"]
        assert window_events, "No window_focus event recorded"
        assert "devwatcher" in window_events[0]["payload"]["title"]

    def test_same_title_does_not_produce_duplicate_event(self, tmp_db):
        mock_win32gui = MagicMock()
        mock_win32gui.GetForegroundWindow.return_value = 1
        mock_win32gui.GetWindowText.return_value = "Stable Title"

        call_count = 0

        def stop_on_second(_n):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                monitor.stop()

        monitor = WindowMonitor(tmp_db, MagicMock())
        with patch.dict(sys.modules, {"win32gui": mock_win32gui}), \
             patch("devwatcher.watchers.window.time.sleep", side_effect=stop_on_second):
            monitor.start()

        events = get_recent_events(tmp_db, limit=10)
        window_events = [e for e in events if e["kind"] == "window_focus"]
        assert len(window_events) == 1  # two polls, one title → one event
