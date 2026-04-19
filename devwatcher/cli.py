import typer

app = typer.Typer()

@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """DevWatcher — rastreador de atividade do desenvolvedor"""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())

@app.command()
def version():
    """Mostra versão."""
    typer.echo("devwatcher 0.1.0")

if __name__ == "__main__":
    app()
