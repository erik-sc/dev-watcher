# DevWatcher

A local-first developer activity tracker for Windows. Runs silently in the background, records file saves, git commits, and active window changes to a local SQLite database, then generates AI-enriched daily and weekly reports.

All data stays on your machine. Nothing is sent anywhere except to the AI provider you configure when you explicitly request a summary.

---

## How it works

```
┌─────────────────────────────────────────────┐
│  devwatcher start                           │
│        │                                    │
│        ▼                                    │
│  Detached daemon process                    │
│  ┌──────────────┐  ┌──────────────────────┐ │
│  │ FileWatcher  │  │ GitPoller            │ │
│  │ (watchdog)   │  │ (gitpython)          │ │
│  └──────┬───────┘  └──────────┬───────────┘ │
│         │                     │             │
│  ┌──────┴─────────────────────┴──────────┐  │
│  │          SQLite (~/.devwatcher/)      │  │
│  └───────────────────────────────────────┘  │
│         │                                   │
│  ┌──────┴───────┐                           │
│  │ WindowMonitor│                           │
│  │ (pywin32)    │                           │
│  └──────────────┘                           │
└─────────────────────────────────────────────┘

  devwatcher today  →  reads SQLite  →  AI summary
```

The daemon spawns as a detached Windows process (no console window). The CLI reads the SQLite file directly — no IPC, no sockets.

---

## Requirements

- Windows 10/11
- Python 3.11+
- An API key for your AI provider (Anthropic by default)

---

## Installation

```bash
pip install -e .
```

On first `start`, DevWatcher creates `~/.devwatcher/config.toml` with defaults and asks for consent before tracking anything.

---

## Usage

```bash
# Start the background tracker
devwatcher start

# Check status and recent events
devwatcher status

# Generate a summary of today's activity (requires DEVWATCHER_API_KEY)
set DEVWATCHER_API_KEY=sk-ant-...
devwatcher today

# Generate a weekly summary
devwatcher week

# Export all saved summaries
devwatcher export --format md       # Markdown (default)
devwatcher export --format json     # JSON
devwatcher export --format csv      # CSV
devwatcher export --output report.md

# Stop the daemon
devwatcher stop
```

---

## Configuration

`~/.devwatcher/config.toml` — created automatically on first start.

```toml
[general]
idle_timeout_minutes = 5    # gap that splits sessions
retention_days = 30         # how long events are kept

[capture]
git_commits = true
file_events = true
active_window = true
watch_dirs = ["~/Documents", "~/Projects"]

[privacy]
redact_secrets = true       # strips API keys, tokens, etc. before writing to DB
global_ignore = ["~/.ssh", "~/.aws", "~/.env*"]

[ai]
provider = "anthropic"
model = "claude-sonnet-4-6"
max_tokens_per_request = 2000
```

### Using a different AI provider

Implement the `AIProvider` protocol and pass your instance to `generate_summary`:

```python
from devwatcher.providers.base import AIProvider

class MyProvider:
    def generate(self, prompt: str, system: str = "") -> str:
        # call your API here
        return response_text
```

---

## Data stored

All data lives in `~/.devwatcher/`.

| File | Contents |
|---|---|
| `config.toml` | Your configuration |
| `db.sqlite` | Events, sessions, summaries, API call log |
| `daemon.pid` | PID of the running daemon (deleted on stop) |
| `daemon.log` | Daemon errors only |
| `reports/` | Markdown files for each generated summary |

### SQLite tables

- **events** — raw activity: `file_save`, `git_commit`, `git_branch_change`, `window_focus`
- **sessions** — aggregated work sessions (grouped by idle gap)
- **summaries** — AI-generated or raw Markdown reports, keyed by period (`day:2026-04-19`, `week:2026-W16`)
- **api_log** — record of each AI call (model, token counts, payload hash — no content)

---

## Privacy

Before any string is written to SQLite, the sanitizer strips:

- Anthropic / OpenAI API keys (`sk-ant-*`, `sk-*`, `sk-proj-*`)
- JWT tokens
- AWS access keys (AKIA, ASIA, AROA, ABIA, ACCA prefixes)
- GitHub tokens (`ghp_`, `gho_`, `ghs_`, `ghu_`, `gha_`)
- Bearer tokens
- Connection strings (user:password@host)
- Generic `key = "value"` / `token = "value"` patterns

Paths in `global_ignore` are never recorded (supports `~` expansion and glob `*` suffix).

---

## Development

```bash
pip install -e ".[dev]"
pytest
```

72 tests across config, DB, sanitizer, providers, processor, all three watchers, daemon, and CLI.

---

## Project structure

```
devwatcher/
├── cli.py          # typer commands
├── config.py       # TOML config + dataclasses + path constants
├── daemon.py       # process management + watcher orchestration
├── db.py           # all SQLite queries
├── processor.py    # session aggregation + AI enrichment
├── sanitizer.py    # secret redaction
├── providers/
│   ├── base.py     # AIProvider protocol
│   └── anthropic.py
└── watchers/
    ├── files.py    # watchdog file events
    ├── git.py      # git commit + branch polling
    └── window.py   # active window via pywin32
```
