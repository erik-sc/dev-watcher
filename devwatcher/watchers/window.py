from __future__ import annotations
import sqlite3
import time

from devwatcher import db as db_module
from devwatcher.config import Config
from devwatcher.sanitizer import sanitize


def get_active_window_title() -> str | None:
    try:
        import win32gui
        hwnd = win32gui.GetForegroundWindow()
        return win32gui.GetWindowText(hwnd) or None
    except Exception:
        return None


class WindowMonitor:
    def __init__(self, conn: sqlite3.Connection, config: Config):
        self._conn = conn
        self._config = config
        self._last_title: str | None = None
        self._running = False

    def start(self) -> None:
        self._running = True
        while self._running:
            title = get_active_window_title()
            if title and title != self._last_title:
                db_module.insert_event(
                    self._conn,
                    "window_focus",
                    None,
                    {"title": sanitize(title)},
                )
                self._last_title = title
            time.sleep(5)

    def stop(self) -> None:
        self._running = False
