import asyncio

import typer
import uvicorn

from trading.db.models import Base
from trading.db.seed import run_seed
from trading.db.session import engine

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


db_app = typer.Typer(help="Database management")
app.add_typer(db_app, name="db")


@db_app.command()
def seed():
    """Seed the database with initial data from config.yaml."""
    run_seed()
    typer.echo("Database seeded.")


@db_app.command()
def init():
    """Create all tables (dev only — use alembic for migrations)."""

    async def _init():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        typer.echo("Tables created.")

    asyncio.run(_init())


if __name__ == "__main__":
    app()
