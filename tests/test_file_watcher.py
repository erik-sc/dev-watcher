import pytest
from unittest.mock import MagicMock
from pathlib import Path
from devwatcher.watchers.files import _FileEventHandler, _detect_project
from devwatcher.db import get_recent_events


def test_file_event_handler_inserts_file_save(tmp_db, tmp_path):
    handler = _FileEventHandler(tmp_db, global_ignore=[])
    mock_event = MagicMock()
    mock_event.is_directory = False
    mock_event.src_path = str(tmp_path / "main.py")
    handler.on_modified(mock_event)
    events = get_recent_events(tmp_db, limit=1)
    assert len(events) == 1
    assert events[0]["kind"] == "file_save"
    assert "main.py" in events[0]["payload"]["path"]


def test_file_event_handler_ignores_directories(tmp_db, tmp_path):
    handler = _FileEventHandler(tmp_db, global_ignore=[])
    mock_event = MagicMock()
    mock_event.is_directory = True
    mock_event.src_path = str(tmp_path / "somedir")
    handler.on_modified(mock_event)
    assert get_recent_events(tmp_db, limit=1) == []


def test_file_event_handler_respects_ignore_patterns(tmp_db, tmp_path):
    handler = _FileEventHandler(tmp_db, global_ignore=[".ssh"])
    mock_event = MagicMock()
    mock_event.is_directory = False
    mock_event.src_path = str(tmp_path / ".ssh" / "id_rsa")
    handler.on_modified(mock_event)
    assert get_recent_events(tmp_db, limit=1) == []


def test_detect_project_finds_git_root(tmp_path):
    git_dir = tmp_path / "myrepo" / ".git"
    git_dir.mkdir(parents=True)
    nested_file = tmp_path / "myrepo" / "src" / "main.py"
    nested_file.parent.mkdir(parents=True)
    nested_file.touch()
    project = _detect_project(nested_file)
    assert str(tmp_path / "myrepo") == project


def test_detect_project_falls_back_to_parent(tmp_path):
    f = tmp_path / "standalone.py"
    f.touch()
    assert _detect_project(f) == str(tmp_path)
