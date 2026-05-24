"""Command-line interface for the code indexer."""

from pathlib import Path

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
@click.argument("repo_path", type=click.Path(exists=True))
def scan(repo_path: str) -> None:
    """Scan a repository and display discovered files."""
    from code_indexer.scanner import RepositoryScanner

    scanner = RepositoryScanner(
        ignore_patterns=settings.ignore_patterns,
        max_file_size_mb=settings.max_file_size_mb,
    )
    result = scanner.scan(Path(repo_path))
    click.echo(f"Scanned {result.total_files} files ({result.total_size} bytes) in {result.scan_time:.2f}s")
    langs: dict[str, int] = {}
    for f in result.files:
        langs[f.language] = langs.get(f.language, 0) + 1
    for lang, count in sorted(langs.items(), key=lambda x: -x[1]):
        click.echo(f"  {lang}: {count}")


@main.command()
@click.argument("repo_path", type=click.Path(exists=True))
@click.option("--db", default=None, help="Database path (overrides DATABASE_URL)")
@click.option("--full", is_flag=True, help="Force full reindex")
def index(repo_path: str, db: str | None, full: bool) -> None:
    """Index or reindex a repository."""
    from code_indexer.indexer import IncrementalReindexer

    db_path = Path(db) if db else Path(settings.database_url.replace("sqlite:///", ""))
    reindexer = IncrementalReindexer(
        repo_root=Path(repo_path),
        db_path=db_path,
    )
    stats = reindexer.full_index() if full else reindexer.run()
    click.echo(f"Indexed  : {stats.files_added} new, {stats.files_updated} updated, "
               f"{stats.files_removed} removed, {stats.files_unchanged} unchanged")
    click.echo(f"Symbols  : {stats.symbols_written}")
    click.echo(f"Refs     : {stats.references_written}")
    click.echo(f"Errors   : {stats.parse_errors}")
    click.echo(f"Duration : {stats.duration_seconds:.2f}s")
    click.echo(f"Full run : {stats.is_full_index}")


@main.command()
@click.argument("query_text")
@click.option("--db", default=None, help="Database path")
@click.option("--budget", default=4000, type=int, help="Token budget")
@click.option("--limit", default=10, type=int, help="Max results")
def query(query_text: str, db: str | None, budget: int, limit: int) -> None:
    """Query the indexed symbols."""
    from code_indexer.retrieval.engine import RetrievalEngine
    from code_indexer.retrieval.models import RetrievalQuery

    db_path = Path(db) if db else Path(settings.database_url.replace("sqlite:///", ""))
    engine = RetrievalEngine(db_path=db_path)

    q = RetrievalQuery(query=query_text, token_budget=budget, limit=limit)
    context = engine.get_related_context(q)

    click.echo(f"Query: {query_text!r}  budget={budget}  found={len(context.snippets)}")
    for snippet in context.snippets:
        click.echo(f"  [{snippet.symbol_type}] {snippet.qualified_name}  ({snippet.file_path}:{snippet.line_start})")


@main.command()
@click.option("--db", default=None, help="Database path (overrides CODE_INDEXER_DB env var)")
def mcp(db: str | None) -> None:
    """Launch the MCP server over stdio for use with Claude Code or claude.ai.

    Add to your Claude Code config (~/.claude.json):

    \b
    {
      "mcpServers": {
        "code-indexer": {
          "command": "code-indexer",
          "args": ["mcp"],
          "env": { "CODE_INDEXER_DB": "/path/to/index.db" }
        }
      }
    }
    """
    import os
    if db:
        os.environ["CODE_INDEXER_DB"] = db
    from code_indexer.mcp.server import run_server
    run_server()


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
