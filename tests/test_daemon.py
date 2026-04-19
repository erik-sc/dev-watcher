import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from devwatcher.daemon import write_pid, read_pid, is_running, start_daemon, stop_daemon


def test_write_and_read_pid(tmp_path, monkeypatch):
    pid_path = tmp_path / "daemon.pid"
    monkeypatch.setattr("devwatcher.daemon.PID_PATH", pid_path)
    write_pid(12345)
    assert read_pid() == 12345


def test_read_pid_returns_none_when_file_missing(tmp_path, monkeypatch):
    monkeypatch.setattr("devwatcher.daemon.PID_PATH", tmp_path / "missing.pid")
    assert read_pid() is None


def test_is_running_returns_false_when_no_pid_file(tmp_path, monkeypatch):
    monkeypatch.setattr("devwatcher.daemon.PID_PATH", tmp_path / "missing.pid")
    assert is_running() is False


def test_is_running_returns_false_for_dead_pid(tmp_path, monkeypatch):
    pid_path = tmp_path / "daemon.pid"
    monkeypatch.setattr("devwatcher.daemon.PID_PATH", pid_path)
    write_pid(999999999)  # PID que não existe
    assert is_running() is False


def test_stop_daemon_returns_false_when_not_running(tmp_path, monkeypatch):
    monkeypatch.setattr("devwatcher.daemon.PID_PATH", tmp_path / "missing.pid")
    assert stop_daemon() is False


def test_stop_daemon_removes_pid_file(tmp_path, monkeypatch):
    pid_path = tmp_path / "daemon.pid"
    monkeypatch.setattr("devwatcher.daemon.PID_PATH", pid_path)
    write_pid(999999999)
    stop_daemon()  # processo não existe, mas remove o PID file
    assert not pid_path.exists()


def test_start_daemon_creates_pid_file(tmp_path, monkeypatch):
    pid_path = tmp_path / "daemon.pid"
    monkeypatch.setattr("devwatcher.daemon.PID_PATH", pid_path)

    mock_proc = MagicMock()
    mock_proc.pid = 9999

    with patch("subprocess.Popen", return_value=mock_proc):
        start_daemon()

    assert pid_path.exists()
    assert read_pid() == 9999
