import typer

app = typer.Typer(help="DevWatcher — rastreador de atividade do desenvolvedor")

@app.command()
def version():
    """Mostra versão."""
    typer.echo("devwatcher 0.1.0")
