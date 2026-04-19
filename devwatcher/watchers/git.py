from __future__ import annotations
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

from git import InvalidGitRepositoryError, Repo

from devwatcher import db as db_module
from devwatcher.config import Config
from devwatcher.sanitizer import sanitize_dict


@dataclass
class _RepoState:
    path: str
    branch: str
    last_sha: str | None


def find_git_repos(watch_dirs: list[Path]) -> list[Repo]:
    repos: list[Repo] = []
    seen: set[str] = set()
    for watch_dir in watch_dirs:
        if not watch_dir.exists():
            continue
        candidates = [watch_dir] + [d for d in watch_dir.iterdir() if d.is_dir()]
        for candidate in candidates:
            try:
                repo = Repo(candidate, search_parent_directories=False)
                key = str(repo.working_dir)
                if key not in seen:
                    seen.add(key)
                    repos.append(repo)
            except (InvalidGitRepositoryError, Exception):
                pass
    return repos


class GitPoller:
    def __init__(
        self, watch_dirs: list[Path], conn: sqlite3.Connection, config: Config
    ):
        self._watch_dirs = watch_dirs
        self._conn = conn
        self._config = config
        self._states: dict[str, _RepoState] = {}
        self._running = False

    def start(self) -> None:
        self._running = True
        self._init_states()
        while self._running:
            self._poll()
            time.sleep(10)

    def stop(self) -> None:
        self._running = False

    def _init_states(self) -> None:
        for repo in find_git_repos(self._watch_dirs):
            try:
                self._states[repo.working_dir] = _RepoState(
                    path=repo.working_dir,
                    branch=repo.active_branch.name,
                    last_sha=(
                        repo.head.commit.hexsha
                        if not repo.head.is_detached
                        else None
                    ),
                )
            except Exception:
                pass

    def _poll(self) -> None:
        for repo in find_git_repos(self._watch_dirs):
            try:
                self._check_repo(repo)
            except Exception:
                pass

    def _check_repo(self, repo: Repo) -> None:
        path = repo.working_dir
        branch = repo.active_branch.name
        sha = repo.head.commit.hexsha if not repo.head.is_detached else None

        state = self._states.get(path)
        if not state:
            self._states[path] = _RepoState(path=path, branch=branch, last_sha=sha)
            return

        if branch != state.branch:
            payload = sanitize_dict({"from": state.branch, "to": branch})
            db_module.insert_event(self._conn, "git_branch", path, payload)
            state.branch = branch

        if sha and sha != state.last_sha:
            commit = repo.head.commit
            payload = sanitize_dict(
                {
                    "message": commit.message.strip(),
                    "sha": sha[:8],
                    "files": list(commit.stats.files.keys())[:20],
                }
            )
            db_module.insert_event(self._conn, "git_commit", path, payload)
            state.last_sha = sha
