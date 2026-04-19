from __future__ import annotations
import re
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

from git import InvalidGitRepositoryError, Repo

from devwatcher import db as db_module
from devwatcher.config import Config
from devwatcher.sanitizer import sanitize, sanitize_dict

# Matches AB#1234 anywhere in a branch name (Azure DevOps work item link)
_AZURE_WI_RE = re.compile(r'AB#(\d+)', re.IGNORECASE)

_DIFF_MAX_CHARS = 4000


def _parse_branch_info(branch_name: str) -> dict:
    """Return work_item_id and work_item_ref if branch contains an Azure DevOps AB# reference."""
    m = _AZURE_WI_RE.search(branch_name)
    if m:
        return {"work_item_id": m.group(1), "work_item_ref": f"AB#{m.group(1)}"}
    return {}


def _get_diff(commit, max_chars: int = _DIFF_MAX_CHARS) -> str | None:
    if not commit.parents:
        return None
    try:
        parts: list[str] = []
        total = 0
        for d in commit.parents[0].diff(commit, create_patch=True):
            chunk = (
                d.diff.decode("utf-8", errors="replace")
                if isinstance(d.diff, bytes)
                else str(d.diff)
            )
            remaining = max_chars - total
            if len(chunk) >= remaining:
                parts.append(chunk[:remaining])
                parts.append("\n[diff truncated]")
                break
            parts.append(chunk)
            total += len(chunk)
        return sanitize("".join(parts)) if parts else None
    except Exception:
        return None


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
            payload = {"from": state.branch, "to": branch}
            payload.update(_parse_branch_info(branch))
            db_module.insert_event(self._conn, "git_branch", path, sanitize_dict(payload))
            state.branch = branch

        if sha and sha != state.last_sha:
            commit = repo.head.commit
            stats = commit.stats.total
            payload: dict = {
                "message": commit.message.strip(),
                "sha": sha[:8],
                "branch": branch,
                "files": list(commit.stats.files.keys())[:20],
                "stats": {
                    "insertions": stats.get("insertions", 0),
                    "deletions": stats.get("deletions", 0),
                    "files": stats.get("files", 0),
                },
            }
            payload.update(_parse_branch_info(branch))
            if self._config.capture.git_diffs:
                diff = _get_diff(commit)
                if diff:
                    payload["diff"] = diff
            db_module.insert_event(self._conn, "git_commit", path, sanitize_dict(payload))
            state.last_sha = sha
