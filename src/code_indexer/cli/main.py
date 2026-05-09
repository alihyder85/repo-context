"""Command-line interface for the code indexer."""

import click
from loguru import logger

from code_indexer.utils.config import settings
from code_indexer.utils.logging import setup_logging


@click.group()
@click.option("--log-level", default=None, help="Set log level")
@click.option("--log-file", default=None, help="Set log file path")
@click.version_option(version="0.1.0")
def main(log_level: str, log_file: str) -> None:
    """AI Code Indexing & Token Optimization System."""
    setup_logging(log_level, log_file)
    logger.info("Code Indexer CLI started")


@main.command()
def scan():
    """Scan a repository for indexing."""
    click.echo("Scanning repository...")
    # TODO: Implement scanning logic
    click.echo("Scan completed!")


@main.command()
def index():
    """Index scanned repository data."""
    click.echo("Indexing repository...")
    # TODO: Implement indexing logic
    click.echo("Indexing completed!")


@main.command()
def query():
    """Query indexed data."""
    click.echo("Querying index...")
    # TODO: Implement query logic
    click.echo("Query completed!")


@main.command()
@click.option("--host", default=None, help="API host")
@click.option("--port", default=None, type=int, help="API port")
def serve(host: str, port: int) -> None:
    """Start the API server."""
    import uvicorn
    from code_indexer.api.app import create_app

    host = host or settings.api_host
    port = port or settings.api_port

    app = create_app()
    logger.info(f"Starting API server on {host}:{port}")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()