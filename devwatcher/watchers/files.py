from __future__ import annotations
import sqlite3
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from devwatcher import db as db_module
from devwatcher.config import Config
from devwatcher.sanitizer import sanitize


class _FileEventHandler(FileSystemEventHandler):
    def __init__(self, conn: sqlite3.Connection, global_ignore: list[str]):
        super().__init__()
        self._conn = conn
        self._global_ignore = global_ignore

    def on_modified(self, event) -> None:
        if event.is_directory:
            return
        if self._should_ignore(event.src_path):
            return
        path = Path(event.src_path)
        project = _detect_project(path)
        db_module.insert_event(
            self._conn, "file_save", project, {"path": sanitize(str(path))}
        )

    def _should_ignore(self, path: str) -> bool:
        normalized = path.replace("\\", "/")
        for pattern in self._global_ignore:
            # Expand ~ to home directory for matching
            expanded = str(Path(pattern.rstrip("*")).expanduser()).replace("\\", "/")
            if pattern.endswith("*"):
                if expanded in normalized:
                    return True
            else:
                clean = pattern.strip("/").replace("~", "").lstrip("/")
                if clean in normalized or expanded in normalized:
                    return True
        return False


def _detect_project(path: Path) -> str | None:
    for parent in path.parents:
        if (parent / ".git").exists():
            return str(parent)
    return str(path.parent)


class FileWatcher:
    def __init__(
        self, watch_dirs: list[Path], conn: sqlite3.Connection, config: Config
    ):
        self._watch_dirs = watch_dirs
        self._conn = conn
        self._config = config
        self._observer: Observer | None = None

    def start(self) -> None:
        handler = _FileEventHandler(self._conn, self._config.privacy.global_ignore)
        self._observer = Observer()
        for d in self._watch_dirs:
            if d.exists():
                self._observer.schedule(handler, str(d), recursive=True)
        self._observer.start()
        self._observer.join()

    def stop(self) -> None:
        if self._observer:
            self._observer.stop()
