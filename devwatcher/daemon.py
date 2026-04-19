from __future__ import annotations
import ctypes
import logging
import os
import subprocess
import sys
import threading
import time

from devwatcher.config import PID_PATH, LOG_PATH, load_config
from devwatcher import db as db_module


def write_pid(pid: int) -> None:
    PID_PATH.parent.mkdir(parents=True, exist_ok=True)
    PID_PATH.write_text(str(pid), encoding="utf-8")


def read_pid() -> int | None:
    if not PID_PATH.exists():
        return None
    try:
        return int(PID_PATH.read_text().strip())
    except (ValueError, OSError):
        return None


def is_running() -> bool:
    pid = read_pid()
    if pid is None:
        return False
    try:
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259
        handle = ctypes.windll.kernel32.OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION, False, pid
        )
        if not handle:
            return False
        exit_code = ctypes.c_ulong(0)
        ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
        ctypes.windll.kernel32.CloseHandle(handle)
        return exit_code.value == STILL_ACTIVE
    except Exception:
        return False


def start_daemon(config_path: str | None = None) -> None:
    DETACHED_PROCESS = 0x00000008
    CREATE_NO_WINDOW = 0x08000000
    cmd = [sys.executable, "-m", "devwatcher.daemon"]
    if config_path:
        cmd += ["--config", config_path]
    proc = subprocess.Popen(
        cmd,
        creationflags=DETACHED_PROCESS | CREATE_NO_WINDOW,
        close_fds=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    write_pid(proc.pid)


def stop_daemon() -> bool:
    pid = read_pid()
    if pid is None:
        return False
    try:
        PROCESS_TERMINATE = 0x0001
        handle = ctypes.windll.kernel32.OpenProcess(PROCESS_TERMINATE, False, pid)
        if handle:
            ctypes.windll.kernel32.TerminateProcess(handle, 0)
            ctypes.windll.kernel32.CloseHandle(handle)
    except Exception:
        pass
    PID_PATH.unlink(missing_ok=True)
    return True


def _setup_logging() -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=str(LOG_PATH),
        level=logging.ERROR,
        format="%(asctime)s %(levelname)s %(message)s",
    )


def main() -> None:
    _setup_logging()
    config = load_config()
    conn = db_module.get_db()
    db_module.init_db(conn)
    write_pid(os.getpid())

    from devwatcher.watchers.files import FileWatcher
    from devwatcher.watchers.git import GitPoller
    from devwatcher.watchers.window import WindowMonitor

    threads: list[threading.Thread] = []

    if config.capture.file_events:
        fw = FileWatcher(config.watch_dirs_expanded, conn, config)
        t = threading.Thread(target=fw.start, daemon=True, name="file-watcher")
        t.start()
        threads.append(t)

    if config.capture.git_commits:
        gp = GitPoller(config.watch_dirs_expanded, conn, config)
        t = threading.Thread(target=gp.start, daemon=True, name="git-poller")
        t.start()
        threads.append(t)

    if config.capture.active_window:
        wm = WindowMonitor(conn, config)
        t = threading.Thread(target=wm.start, daemon=True, name="window-monitor")
        t.start()
        threads.append(t)

    try:
        while True:
            time.sleep(3600)
            db_module.purge_old_events(conn, config.general.retention_days)
    except Exception as exc:
        logging.error("Daemon crashed: %s", exc)
    finally:
        PID_PATH.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
