import time
import pytest
from devwatcher.processor import Session, aggregate_sessions, build_prompt, format_raw_summary


def _ev(kind, project, ts_offset=0, payload=None):
    return {
        "kind": kind,
        "project": project,
        "ts": int(time.time()) + ts_offset,
        "payload": payload,
        "id": 1,
    }


def test_aggregate_sessions_empty():
    assert aggregate_sessions([]) == []


def test_aggregate_sessions_single_continuous_session():
    events = [
        _ev("file_save", "/proj", 0),
        _ev("file_save", "/proj", 30),
        _ev("git_commit", "/proj", 60, {"message": "feat: auth", "files": ["auth.py"]}),
    ]
    sessions = aggregate_sessions(events, idle_timeout_minutes=5)
    assert len(sessions) == 1
    assert sessions[0].project == "/proj"
    assert sessions[0].duration_s == 60


def test_aggregate_sessions_idle_gap_splits_into_two():
    events = [
        _ev("file_save", "/p", 0),
        _ev("file_save", "/p", 400),  # 400s > 5min idle
    ]
    sessions = aggregate_sessions(events, idle_timeout_minutes=5)
    assert len(sessions) == 2


def test_aggregate_sessions_project_is_majority():
    events = [
        _ev("file_save", "/proj-a", 0),
        _ev("file_save", "/proj-a", 10),
        _ev("file_save", "/proj-b", 20),
    ]
    sessions = aggregate_sessions(events, idle_timeout_minutes=5)
    assert sessions[0].project == "/proj-a"


def test_session_commits_filters_git_commit_events():
    events = [
        _ev("file_save", "/p", 0),
        _ev("git_commit", "/p", 10, {"message": "feat: add auth", "files": ["auth.py"]}),
    ]
    sessions = aggregate_sessions(events)
    assert len(sessions[0].commits) == 1
    assert sessions[0].commits[0]["payload"]["message"] == "feat: add auth"


def test_build_prompt_includes_project_name_and_duration():
    events = [_ev("file_save", "/my/project", 0), _ev("file_save", "/my/project", 120)]
    sessions = aggregate_sessions(events)
    prompt = build_prompt(sessions)
    assert "/my/project" in prompt
    assert "2 min" in prompt


def test_build_prompt_includes_commit_message():
    events = [
        _ev("git_commit", "/p", 0, {"message": "feat: add login", "files": ["login.py"]})
    ]
    sessions = aggregate_sessions(events)
    prompt = build_prompt(sessions)
    assert "feat: add login" in prompt
    assert "login.py" in prompt


def test_format_raw_summary_includes_project_and_total():
    events = [
        _ev("file_save", "/proj", 0),
        _ev("file_save", "/proj", 120),
    ]
    sessions = aggregate_sessions(events, idle_timeout_minutes=5)
    summary = format_raw_summary(sessions)
    assert "/proj" in summary
    assert "Total" in summary
