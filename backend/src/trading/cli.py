import typer
import uvicorn

app = typer.Typer(help="Multi-agent trading system CLI")


@app.command()
def serve(host: str = "127.0.0.1", port: int = 8000, reload: bool = True):
    """Start the FastAPI server."""
    uvicorn.run("trading.api.app:app", host=host, port=port, reload=reload)


agent_app = typer.Typer(help="Run trading agents")
app.add_typer(agent_app, name="run")


@agent_app.command()
def ingestion():
    """Run the data ingestion agent."""
    typer.echo("not implemented")


@agent_app.command()
def signal():
    """Run the signal generation agent."""
    typer.echo("not implemented")


@agent_app.command()
def risk():
    """Run the risk management agent."""
    typer.echo("not implemented")


@agent_app.command()
def execution():
    """Run the order execution agent."""
    typer.echo("not implemented")


if __name__ == "__main__":
    app()
