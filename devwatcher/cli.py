from __future__ import annotations
import csv
import io
import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import typer

app = typer.Typer(help="DevWatcher — rastreador de atividade do desenvolvedor")


def _resolve_api_key(config_key: str) -> str:
    key = os.environ.get("DEVWATCHER_API_KEY", "") or config_key
    if not key:
        typer.echo(
            "Erro: chave de API não configurada.\n"
            "Defina DEVWATCHER_API_KEY ou adicione api_key em [ai] no config.toml.",
            err=True,
        )
        raise typer.Exit(1)
    return key


def _make_provider(config):
    from devwatcher.config import AIConfig
    api_key = _resolve_api_key(config.ai.api_key)
    if config.ai.provider == "gemini":
        from devwatcher.providers.gemini import GeminiProvider
        return GeminiProvider(api_key, config.ai.model, config.ai.max_tokens_per_request)
    from devwatcher.providers.anthropic import AnthropicProvider
    return AnthropicProvider(api_key, config.ai.model, config.ai.max_tokens_per_request)


@app.command()
def start() -> None:
    """Inicia o daemon de rastreamento em background."""
    from devwatcher import daemon
    from devwatcher.config import load_config, write_default_config, CONFIG_PATH

    if daemon.is_running():
        typer.echo("DevWatcher já está rodando.")
        raise typer.Exit(0)

    if not CONFIG_PATH.exists():
        _first_run_consent()
        write_default_config()

    daemon.start_daemon()
    typer.echo("DevWatcher iniciado.")


def _first_run_consent() -> None:
    typer.echo("\n=== DevWatcher — Primeiro uso ===\n")
    typer.echo("O DevWatcher irá capturar:")
    typer.echo("  + Arquivos salvos (caminho, não conteúdo)")
    typer.echo("  + Commits git (mensagem e lista de arquivos)")
    typer.echo("  + Trocas de branch git")
    typer.echo("  + Janela ativa")
    typer.echo("\nTodos os dados ficam em: ~/.devwatcher/")
    typer.echo("Enriquecimento usa o provider configurado em [ai].\n")
    if not typer.confirm("Deseja continuar?"):
        typer.echo("Abortado.")
        raise typer.Exit(0)


@app.command()
def stop() -> None:
    """Para o daemon."""
    from devwatcher import daemon

    if daemon.stop_daemon():
        typer.echo("DevWatcher parado.")
    else:
        typer.echo("DevWatcher não estava rodando.")


@app.command()
def status() -> None:
    """Mostra status do daemon e eventos recentes."""
    from devwatcher import daemon, db as db_module

    running = daemon.is_running()
    typer.echo(f"Status: {'rodando' if running else 'parado'}")

    conn = db_module.get_db()
    db_module.init_db(conn)

    events = db_module.get_recent_events(conn, limit=10)
    if events:
        typer.echo(f"\nÚltimos {len(events)} evento(s):")
        for e in events:
            ts = datetime.fromtimestamp(e["ts"]).strftime("%H:%M:%S")
            typer.echo(f"  [{ts}] {e['kind']} — {e['project'] or '-'}")
    else:
        typer.echo("Nenhum evento registrado.")

    since_24h = int(time.time()) - 86400
    api_count = db_module.get_api_call_count(conn, since_24h)
    typer.echo(f"\nChamadas à API (últimas 24h): {api_count}")


@app.command()
def today() -> None:
    """Gera resumo do dia atual com enriquecimento por IA."""
    _generate_period_summary("day")


@app.command()
def week() -> None:
    """Gera resumo da semana atual com enriquecimento por IA."""
    _generate_period_summary("week")


def _generate_period_summary(period_type: str) -> None:
    from devwatcher import db as db_module
    from devwatcher.config import load_config
    from devwatcher.processor import generate_summary

    config = load_config()
    conn = db_module.get_db()
    db_module.init_db(conn)

    now = datetime.now()
    if period_type == "day":
        since_ts = int(datetime(now.year, now.month, now.day).timestamp())
        period = f"day:{now.strftime('%Y-%m-%d')}"
    else:
        monday = now - timedelta(days=now.weekday())
        since_ts = int(datetime(monday.year, monday.month, monday.day).timestamp())
        period = f"week:{now.strftime('%Y-W%W')}"

    provider = _make_provider(config)

    typer.echo("Gerando resumo...")
    content = generate_summary(provider, conn, period, since_ts, config)
    typer.echo(content)


@app.command()
def export(
    format: str = typer.Option("md", help="Formato de saída: md, csv, json"),
    output: Optional[str] = typer.Option(None, help="Arquivo de saída (padrão: stdout)"),
) -> None:
    """Exporta resumos salvos."""
    from devwatcher import db as db_module

    conn = db_module.get_db()
    db_module.init_db(conn)

    rows = conn.execute(
        "SELECT period, content_md, created_at FROM summaries ORDER BY created_at DESC"
    ).fetchall()

    if format == "json":
        data = [
            {"period": r["period"], "content": r["content_md"], "created_at": r["created_at"]}
            for r in rows
        ]
        result = json.dumps(data, ensure_ascii=False, indent=2)
    elif format == "csv":
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["period", "created_at", "content_md"])
        for r in rows:
            writer.writerow([r["period"], r["created_at"], r["content_md"]])
        result = buf.getvalue()
    else:
        result = "\n\n---\n\n".join(r["content_md"] for r in rows)

    if output:
        Path(output).write_text(result, encoding="utf-8")
        typer.echo(f"Exportado para {output}")
    else:
        typer.echo(result)
