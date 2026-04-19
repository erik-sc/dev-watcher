"""Database module for DevWatcher."""
from __future__ import annotations
import json
import sqlite3
import time
from pathlib import Path


def get_db(db_path: Path | None = None) -> sqlite3.Connection:
    """Get a database connection."""
    from devwatcher.config import DB_PATH
    path = db_path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """Initialize the database."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS events (
            id      INTEGER PRIMARY KEY,
            ts      INTEGER NOT NULL,
            kind    TEXT NOT NULL,
            project TEXT,
            payload TEXT
        );
        CREATE TABLE IF NOT EXISTS sessions (
            id         INTEGER PRIMARY KEY,
            started_at INTEGER NOT NULL,
            ended_at   INTEGER,
            project    TEXT,
            duration_s INTEGER,
            category   TEXT
        );
        CREATE TABLE IF NOT EXISTS summaries (
            id         INTEGER PRIMARY KEY,
            created_at INTEGER NOT NULL,
            period     TEXT NOT NULL,
            content_md TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS api_log (
            id          INTEGER PRIMARY KEY,
            ts          INTEGER NOT NULL,
            provider    TEXT,
            model       TEXT,
            tokens_in   INTEGER,
            tokens_out  INTEGER,
            payload_md5 TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);
        CREATE INDEX IF NOT EXISTS idx_api_log_ts ON api_log(ts);
        CREATE INDEX IF NOT EXISTS idx_summaries_period ON summaries(period);
    """)
    conn.commit()


def insert_event(
    conn: sqlite3.Connection,
    kind: str,
    project: str | None,
    payload: dict | None,
) -> None:
    """Insert an event into the database."""
    conn.execute(
        "INSERT INTO events (ts, kind, project, payload) VALUES (?, ?, ?, ?)",
        (int(time.time()), kind, project, json.dumps(payload) if payload else None),
    )
    conn.commit()


def get_recent_events(conn: sqlite3.Connection, limit: int = 10) -> list[dict]:
    """Get recent events in ascending order by timestamp."""
    rows = conn.execute(
        "SELECT id, ts, kind, project, payload FROM events ORDER BY ts DESC, id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [_row_to_event(r) for r in reversed(rows)]


def get_events_since(conn: sqlite3.Connection, since_ts: int) -> list[dict]:
    """Get events since a given timestamp in ascending order (inclusive lower bound)."""
    rows = conn.execute(
        "SELECT id, ts, kind, project, payload FROM events WHERE ts >= ? ORDER BY ts ASC",
        (since_ts,),
    ).fetchall()
    return [_row_to_event(r) for r in rows]


def _row_to_event(row: sqlite3.Row) -> dict:
    """Convert a database row to an event dict."""
    d = dict(row)
    if d.get("payload"):
        d["payload"] = json.loads(d["payload"])
    return d


def insert_summary(conn: sqlite3.Connection, period: str, content_md: str) -> int:
    """Insert a summary and return its ID."""
    cur = conn.execute(
        "INSERT INTO summaries (created_at, period, content_md) VALUES (?, ?, ?)",
        (int(time.time()), period, content_md),
    )
    conn.commit()
    return cur.lastrowid


def get_summary(conn: sqlite3.Connection, period: str) -> str | None:
    """Get the most recent summary for a given period."""
    row = conn.execute(
        "SELECT content_md FROM summaries WHERE period = ? ORDER BY created_at DESC LIMIT 1",
        (period,),
    ).fetchone()
    return row["content_md"] if row else None


def log_api_call(
    conn: sqlite3.Connection,
    provider: str,
    model: str,
    tokens_in: int,
    tokens_out: int,
    payload_md5: str,
) -> None:
    """Log an API call."""
    conn.execute(
        "INSERT INTO api_log (ts, provider, model, tokens_in, tokens_out, payload_md5)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (int(time.time()), provider, model, tokens_in, tokens_out, payload_md5),
    )
    conn.commit()


def get_api_call_count(conn: sqlite3.Connection, since_ts: int) -> int:
    """Get count of API calls since a given timestamp."""
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM api_log WHERE ts >= ?", (since_ts,)
    ).fetchone()
    return row["cnt"]


def purge_old_events(conn: sqlite3.Connection, retention_days: int) -> None:
    """Delete events and summaries older than retention_days."""
    cutoff = int(time.time()) - (retention_days * 86400)
    conn.execute("DELETE FROM events WHERE ts < ?", (cutoff,))
    conn.execute("DELETE FROM summaries WHERE created_at < ?", (cutoff,))
    conn.commit()
