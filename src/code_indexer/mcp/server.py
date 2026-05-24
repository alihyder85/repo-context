"""MCP server for the code indexer.

Exposes the retrieval engine as Claude tools via the Model Context Protocol.

## Claude Code configuration (~/.claude.json or project .mcp.json)

```json
{
  "mcpServers": {
    "code-indexer": {
      "command": "code-indexer",
      "args": ["mcp"],
      "env": { "CODE_INDEXER_DB": "/absolute/path/to/index.db" }
    }
  }
}
```

Run `code-indexer index <repo>` first to create the database.
"""
from __future__ import annotations

import asyncio
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

from code_indexer.mcp import tools as _tools

server = Server("code-indexer")


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="get_context",
            description=(
                "Fetch token-budgeted code context for a query. "
                "Returns ranked snippets with file paths, line ranges, and source code. "
                "Use this first when the user asks about code."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Symbol name or free-text question"},
                    "token_budget": {"type": "integer", "default": 6000, "description": "Max tokens to return"},
                    "language": {"type": "string", "description": "Filter by language (python, typescript, java, ...)"},
                },
                "required": ["query"],
            },
        ),
        types.Tool(
            name="search_symbols",
            description=(
                "Full-text search across symbol names, signatures, and docstrings. "
                "Use when you need to discover what exists in the codebase."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "FTS5 search query"},
                    "limit": {"type": "integer", "default": 20},
                },
                "required": ["query"],
            },
        ),
        types.Tool(
            name="find_symbol",
            description="Exact or prefix lookup for a symbol by name.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "symbol_type": {"type": "string", "description": "function|class|method|variable|import"},
                    "language": {"type": "string"},
                },
                "required": ["name"],
            },
        ),
        types.Tool(
            name="read_snippet",
            description="Read raw source lines from a file by path and line range.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string"},
                    "line_start": {"type": "integer"},
                    "line_end": {"type": "integer"},
                },
                "required": ["file_path", "line_start", "line_end"],
            },
        ),
        types.Tool(
            name="get_dependencies",
            description="Traverse the dependency graph from a symbol ID up to max_depth hops.",
            inputSchema={
                "type": "object",
                "properties": {
                    "symbol_id": {"type": "integer"},
                    "max_depth": {"type": "integer", "default": 2},
                },
                "required": ["symbol_id"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[types.TextContent]:
    try:
        result = _dispatch(name, arguments)
    except FileNotFoundError as exc:
        result = f"Error: {exc}"
    except Exception as exc:
        result = f"Tool {name!r} failed: {exc}"
    return [types.TextContent(type="text", text=result)]


def _dispatch(name: str, args: dict[str, Any]) -> str:
    if name == "get_context":
        return _tools.get_context(
            query=args["query"],
            token_budget=args.get("token_budget", 6000),
            language=args.get("language"),
        )
    if name == "search_symbols":
        return _tools.search_symbols(
            query=args["query"],
            limit=args.get("limit", 20),
        )
    if name == "find_symbol":
        return _tools.find_symbol(
            name=args["name"],
            symbol_type=args.get("symbol_type"),
            language=args.get("language"),
        )
    if name == "read_snippet":
        return _tools.read_snippet(
            file_path=args["file_path"],
            line_start=args["line_start"],
            line_end=args["line_end"],
        )
    if name == "get_dependencies":
        return _tools.get_dependencies(
            symbol_id=args["symbol_id"],
            max_depth=args.get("max_depth", 2),
        )
    return f"Unknown tool: {name!r}"


def run_server() -> None:
    """Launch the MCP server over stdio (blocking)."""
    asyncio.run(_serve())


async def _serve() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())
