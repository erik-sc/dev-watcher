import sys
from unittest.mock import MagicMock, patch

import pytest

from devwatcher.db import get_recent_events
from devwatcher.watchers.window import WindowMonitor, get_active_window_title


def test_get_active_window_title_returns_none_on_exception():
    mock_win32gui = MagicMock()
    mock_win32gui.GetForegroundWindow.side_effect = Exception("no hwnd")
    with patch.dict(sys.modules, {"win32gui": mock_win32gui}):
        result = get_active_window_title()
    assert result is None


def test_get_active_window_title_returns_none_when_empty():
    mock_win32gui = MagicMock()
    mock_win32gui.GetForegroundWindow.return_value = 0
    mock_win32gui.GetWindowText.return_value = ""
    with patch.dict(sys.modules, {"win32gui": mock_win32gui}):
        result = get_active_window_title()
    assert result is None


def _one_iteration(monitor, win32gui_mock):
    """Run exactly one loop iteration then stop."""
    def stop_after_sleep(_n):
        monitor.stop()

    with patch.dict(sys.modules, {"win32gui": win32gui_mock}), \
         patch("devwatcher.watchers.window.time.sleep", side_effect=stop_after_sleep):
        monitor.start()


def test_window_monitor_inserts_event_on_new_title(tmp_db):
    mock_config = MagicMock()
    mock_win32gui = MagicMock()
    mock_win32gui.GetForegroundWindow.return_value = 1
    mock_win32gui.GetWindowText.return_value = "VS Code — main.py"

    monitor = WindowMonitor(tmp_db, mock_config)
    _one_iteration(monitor, mock_win32gui)

    events = get_recent_events(tmp_db, limit=10)
    window_events = [e for e in events if e["kind"] == "window_focus"]
    assert len(window_events) == 1
    assert "VS Code" in window_events[0]["payload"]["title"]


def test_window_monitor_skips_unchanged_title(tmp_db):
    mock_config = MagicMock()
    mock_win32gui = MagicMock()
    mock_win32gui.GetForegroundWindow.return_value = 1
    mock_win32gui.GetWindowText.return_value = "Same Title"

    sleep_calls = 0

    def stop_on_second_sleep(_n):
        nonlocal sleep_calls
        sleep_calls += 1
        if sleep_calls >= 2:
            monitor.stop()

    monitor = WindowMonitor(tmp_db, mock_config)
    with patch.dict(sys.modules, {"win32gui": mock_win32gui}), \
         patch("devwatcher.watchers.window.time.sleep", side_effect=stop_on_second_sleep):
        monitor.start()

    events = get_recent_events(tmp_db, limit=10)
    window_events = [e for e in events if e["kind"] == "window_focus"]
    assert len(window_events) == 1
