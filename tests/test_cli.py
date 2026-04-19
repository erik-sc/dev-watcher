import pytest
import json
from unittest.mock import MagicMock, patch
from typer.testing import CliRunner
from devwatcher.cli import app
from devwatcher.db import insert_summary, insert_event

runner = CliRunner()


def test_start_when_already_running():
    with patch("devwatcher.daemon.is_running", return_value=True):
        result = runner.invoke(app, ["start"])
    assert result.exit_code == 0
    assert "já está rodando" in result.output


def test_stop_when_daemon_is_running():
    with patch("devwatcher.daemon.stop_daemon", return_value=True):
        result = runner.invoke(app, ["stop"])
    assert result.exit_code == 0
    assert "parado" in result.output


def test_stop_when_daemon_is_not_running():
    with patch("devwatcher.daemon.stop_daemon", return_value=False):
        result = runner.invoke(app, ["stop"])
    assert result.exit_code == 0
    assert "não estava rodando" in result.output


def test_status_shows_daemon_state(tmp_db, tmp_path, monkeypatch):
    monkeypatch.setattr("devwatcher.config.DB_PATH", tmp_path / "test.sqlite")
    insert_event(tmp_db, "file_save", "/proj", {"path": "/proj/main.py"})

    with patch("devwatcher.daemon.is_running", return_value=True), \
         patch("devwatcher.db.get_db", return_value=tmp_db):
        result = runner.invoke(app, ["status"])

    assert result.exit_code == 0
    assert "rodando" in result.output
    assert "file_save" in result.output


def test_today_calls_generate_summary(tmp_db, tmp_path, monkeypatch):
    monkeypatch.setenv("DEVWATCHER_API_KEY", "fake-key")
    monkeypatch.setattr("devwatcher.config.DEVWATCHER_DIR", tmp_path)
    insert_event(tmp_db, "file_save", "/proj", {"path": "/proj/main.py"})

    mock_provider = MagicMock()
    mock_provider.generate.return_value = "# Resumo\nFiz coisas hoje."

    with patch("devwatcher.db.get_db", return_value=tmp_db), \
         patch("devwatcher.providers.anthropic.AnthropicProvider", return_value=mock_provider):
        result = runner.invoke(app, ["today"])

    assert result.exit_code == 0
    assert "Resumo" in result.output


def test_export_json(tmp_db):
    insert_summary(tmp_db, "day:2026-04-19", "# Report\nDid stuff.")

    with patch("devwatcher.db.get_db", return_value=tmp_db):
        result = runner.invoke(app, ["export", "--format", "json"])

    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data[0]["period"] == "day:2026-04-19"


def test_export_csv(tmp_db):
    insert_summary(tmp_db, "day:2026-04-19", "# Report")

    with patch("devwatcher.db.get_db", return_value=tmp_db):
        result = runner.invoke(app, ["export", "--format", "csv"])

    assert result.exit_code == 0
    assert "day:2026-04-19" in result.output


def test_export_md(tmp_db):
    insert_summary(tmp_db, "day:2026-04-19", "# My Report")

    with patch("devwatcher.db.get_db", return_value=tmp_db):
        result = runner.invoke(app, ["export", "--format", "md"])

    assert result.exit_code == 0
    assert "# My Report" in result.output
