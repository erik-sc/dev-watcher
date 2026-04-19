from __future__ import annotations
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

DEVWATCHER_DIR = Path.home() / ".devwatcher"
CONFIG_PATH = DEVWATCHER_DIR / "config.toml"
DB_PATH = DEVWATCHER_DIR / "db.sqlite"
PID_PATH = DEVWATCHER_DIR / "daemon.pid"
LOG_PATH = DEVWATCHER_DIR / "daemon.log"
REPORTS_DIR = DEVWATCHER_DIR / "reports"

DEFAULT_CONFIG = """\
[general]
language = "pt-BR"
auto_summary = true
summary_time = "18:00"
idle_timeout_minutes = 5
retention_days = 30

[capture]
git_commits = true
git_diffs = false
file_events = true
terminal_commands = false
active_window = true
watch_dirs = ["~/Documents", "~/Projects"]

[privacy]
redact_secrets = true
send_source_code = false
api_call_log = true
global_ignore = ["~/.ssh", "~/.aws", "~/.env*"]

[ai]
provider = "anthropic"
model = "claude-sonnet-4-6"
api_key = ""
base_url = ""
max_tokens_per_request = 2000
"""


@dataclass
class GeneralConfig:
    language: str = "pt-BR"
    auto_summary: bool = True
    summary_time: str = "18:00"
    idle_timeout_minutes: int = 5
    retention_days: int = 30


@dataclass
class CaptureConfig:
    git_commits: bool = True
    git_diffs: bool = False
    file_events: bool = True
    terminal_commands: bool = False
    active_window: bool = True
    watch_dirs: list[str] = field(
        default_factory=lambda: ["~/Documents", "~/Projects"]
    )


@dataclass
class PrivacyConfig:
    redact_secrets: bool = True
    send_source_code: bool = False
    api_call_log: bool = True
    global_ignore: list[str] = field(
        default_factory=lambda: ["~/.ssh", "~/.aws", "~/.env*"]
    )


@dataclass
class AIConfig:
    provider: str = "anthropic"
    model: str = "claude-sonnet-4-6"
    api_key: str = ""
    base_url: str = ""
    max_tokens_per_request: int = 2000


@dataclass
class Config:
    general: GeneralConfig = field(default_factory=GeneralConfig)
    capture: CaptureConfig = field(default_factory=CaptureConfig)
    privacy: PrivacyConfig = field(default_factory=PrivacyConfig)
    ai: AIConfig = field(default_factory=AIConfig)

    @property
    def watch_dirs_expanded(self) -> list[Path]:
        return [Path(d).expanduser().resolve() for d in self.capture.watch_dirs]


def load_config(config_path: Path | None = None) -> Config:
    path = config_path or CONFIG_PATH
    if not path.exists():
        return Config()
    with open(path, "rb") as f:  # tomllib requires binary mode
        data = tomllib.load(f)
    return _parse_config(data)


def _parse_config(data: dict) -> Config:
    try:
        general = GeneralConfig(**data.get("general", {}))
    except TypeError as exc:
        raise ValueError(f"Invalid key in [general] section: {exc}") from exc
    try:
        capture = CaptureConfig(**data.get("capture", {}))
    except TypeError as exc:
        raise ValueError(f"Invalid key in [capture] section: {exc}") from exc
    try:
        privacy = PrivacyConfig(**data.get("privacy", {}))
    except TypeError as exc:
        raise ValueError(f"Invalid key in [privacy] section: {exc}") from exc
    try:
        ai = AIConfig(**data.get("ai", {}))
    except TypeError as exc:
        raise ValueError(f"Invalid key in [ai] section: {exc}") from exc
    return Config(general=general, capture=capture, privacy=privacy, ai=ai)


def write_default_config(config_path: Path | None = None) -> None:
    path = config_path or CONFIG_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(DEFAULT_CONFIG, encoding="utf-8")
