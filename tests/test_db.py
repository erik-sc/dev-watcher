import time
import pytest
from devwatcher.db import (
    get_db, init_db, insert_event, get_recent_events, get_events_since,
    insert_summary, get_summary, log_api_call, get_api_call_count, purge_old_events,
)


def test_init_creates_all_tables(tmp_db):
    tables = {
        row[0]
        for row in tmp_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert {"events", "sessions", "summaries", "api_log"} <= tables


def test_insert_and_retrieve_event(tmp_db):
    insert_event(tmp_db, "file_save", "/my/project", {"path": "/my/file.py"})
    events = get_recent_events(tmp_db, limit=1)
    assert len(events) == 1
    assert events[0]["kind"] == "file_save"
    assert events[0]["project"] == "/my/project"
    assert events[0]["payload"]["path"] == "/my/file.py"


def test_get_recent_events_returns_ascending_order(tmp_db):
    insert_event(tmp_db, "file_save", "/p", {"f": "a"})
    time.sleep(0.01)
    insert_event(tmp_db, "git_commit", "/p", {"message": "feat"})
    events = get_recent_events(tmp_db, limit=2)
    assert events[0]["kind"] == "file_save"
    assert events[1]["kind"] == "git_commit"


def test_get_events_since_filters_by_timestamp(tmp_db):
    insert_event(tmp_db, "file_save", "/p", None)
    old_ts = int(time.time()) - 200
    tmp_db.execute(
        "UPDATE events SET ts = ? WHERE id = (SELECT MAX(id) FROM events)", (old_ts,)
    )
    tmp_db.commit()
    insert_event(tmp_db, "git_commit", "/p", None)
    events = get_events_since(tmp_db, int(time.time()) - 100)
    assert len(events) == 1
    assert events[0]["kind"] == "git_commit"


def test_insert_and_get_summary(tmp_db):
    insert_summary(tmp_db, "day:2026-04-19", "# Report\nDid stuff.")
    assert get_summary(tmp_db, "day:2026-04-19") == "# Report\nDid stuff."


def test_get_summary_returns_none_when_missing(tmp_db):
    assert get_summary(tmp_db, "day:2099-01-01") is None


def test_log_api_call_and_count(tmp_db):
    since = int(time.time()) - 1
    log_api_call(tmp_db, "anthropic", "claude-sonnet-4-6", 100, 200, "abc")
    log_api_call(tmp_db, "anthropic", "claude-sonnet-4-6", 50, 100, "def")
    assert get_api_call_count(tmp_db, since) == 2


def test_purge_old_events_removes_stale_records(tmp_db):
    insert_event(tmp_db, "file_save", "/p", None)
    old_ts = int(time.time()) - (40 * 86400)
    tmp_db.execute(
        "UPDATE events SET ts = ? WHERE id = (SELECT MAX(id) FROM events)", (old_ts,)
    )
    tmp_db.commit()
    insert_event(tmp_db, "git_commit", "/p", None)
    purge_old_events(tmp_db, retention_days=30)
    events = get_recent_events(tmp_db, limit=10)
    assert len(events) == 1
    assert events[0]["kind"] == "git_commit"
