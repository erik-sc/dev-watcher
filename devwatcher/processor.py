from __future__ import annotations
import hashlib
import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime

from devwatcher.providers.base import AIProvider

SYSTEM_PROMPT = """Você é um assistente de documentação de desenvolvimento.
Recebe logs de atividade de um desenvolvedor e gera:

1. RESUMO NARRATIVO: O que foi feito, em linguagem natural, como se o dev estivesse contando para um colega.

2. CLASSIFICAÇÃO: Categorize cada sessão em uma das categorias: coding, debugging, refactoring, devops, code-review, research, documentation, meetings, other.

3. STANDUP: Gere um texto curto no formato:
   - Ontem eu...
   - Hoje vou...
   - Bloqueios: ...

4. CHANGELOG (se houver commits): Liste as mudanças significativas em formato de changelog.

Regras:
- Seja conciso e técnico, sem enrolação.
- Não invente informações que não estão nos logs.
- Se os logs forem ambíguos, diga "atividade não clara" em vez de chutar.
- Nunca inclua tokens, secrets ou dados sensíveis no output mesmo que apareçam nos logs.
- Responda em português ou inglês conforme a língua dos commits do dev."""


@dataclass
class Session:
    project: str | None
    started_at: int
    ended_at: int
    events: list[dict] = field(default_factory=list, repr=False)

    @property
    def duration_s(self) -> int:
        return max(0, self.ended_at - self.started_at)

    @property
    def commits(self) -> list[dict]:
        return [e for e in self.events if e["kind"] == "git_commit"]


def aggregate_sessions(
    events: list[dict], idle_timeout_minutes: int = 5
) -> list[Session]:
    if not events:
        return []
    idle_gap_s = idle_timeout_minutes * 60
    sessions: list[Session] = []
    current: list[dict] = [events[0]]
    for event in events[1:]:
        if event["ts"] - current[-1]["ts"] > idle_gap_s:
            sessions.append(_make_session(current))
            current = [event]
        else:
            current.append(event)
    sessions.append(_make_session(current))
    return sessions


def _make_session(events: list[dict]) -> Session:
    projects = [e["project"] for e in events if e.get("project")]
    project = max(set(projects), key=projects.count) if projects else None
    return Session(
        project=project,
        started_at=events[0]["ts"],
        ended_at=events[-1]["ts"],
        events=events,
    )


def build_prompt(sessions: list[Session]) -> str:
    lines = ["Logs de atividade do desenvolvedor:\n"]
    for i, s in enumerate(sessions, 1):
        start = datetime.fromtimestamp(s.started_at).strftime("%H:%M")
        end = datetime.fromtimestamp(s.ended_at).strftime("%H:%M")
        minutes = s.duration_s // 60
        lines.append(f"## Sessão {i}: {s.project or 'desconhecido'}")
        lines.append(f"Horário: {start} — {end} ({minutes} min)")
        for c in s.commits:
            p = c.get("payload") or {}
            lines.append(f"- commit: {p.get('message', 'sem mensagem')}")
            if p.get("files"):
                lines.append(f"  arquivos: {', '.join(p['files'][:5])}")
        file_saves = sum(1 for e in s.events if e["kind"] == "file_save")
        if file_saves:
            lines.append(f"- {file_saves} arquivo(s) salvo(s)")
        lines.append("")
    return "\n".join(lines)


def format_raw_summary(sessions: list[Session]) -> str:
    lines = ["# Resumo de Atividade (sem enriquecimento por IA)\n"]
    total_s = sum(s.duration_s for s in sessions)
    lines.append(f"**Total:** {total_s // 3600}h{(total_s % 3600) // 60}min\n")
    for s in sessions:
        start = datetime.fromtimestamp(s.started_at).strftime("%H:%M")
        end = datetime.fromtimestamp(s.ended_at).strftime("%H:%M")
        minutes = s.duration_s // 60
        lines.append(
            f"- **{s.project or 'desconhecido'}** {start}–{end} ({minutes} min)"
        )
        for c in s.commits:
            p = c.get("payload") or {}
            lines.append(f"  - commit: {p.get('message', '')}")
    return "\n".join(lines)


def generate_summary(
    provider: AIProvider,
    conn: sqlite3.Connection,
    period: str,
    since_ts: int,
    config,
) -> str:
    from devwatcher import db as db_module
    from devwatcher.config import DEVWATCHER_DIR

    events = db_module.get_events_since(conn, since_ts)
    if not events:
        return "Nenhuma atividade registrada para este período."

    sessions = aggregate_sessions(events, config.general.idle_timeout_minutes)
    prompt = build_prompt(sessions)

    try:
        content_md = provider.generate(prompt, system=SYSTEM_PROMPT)
        payload_md5 = hashlib.md5(prompt.encode()).hexdigest()
        db_module.log_api_call(
            conn, config.ai.provider, config.ai.model, 0, 0, payload_md5
        )
    except Exception as exc:
        content_md = format_raw_summary(sessions)
        content_md += f"\n\n---\n*Enriquecimento por IA indisponível: {exc}*"

    db_module.insert_summary(conn, period, content_md)

    reports_dir = DEVWATCHER_DIR / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    filename = period.replace(":", "-").replace("day-", "") + ".md"
    (reports_dir / filename).write_text(content_md, encoding="utf-8")

    return content_md
