"""Tool implementations for the MCP server.

Each function maps to one MCP tool. All database access goes through
RetrievalEngine — no raw SQL here.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from code_indexer.retrieval.engine import RetrievalEngine
from code_indexer.retrieval.models import RetrievalQuery


def _db_path() -> Path:
    """Resolve the SQLite database path from env or settings."""
    raw = os.environ.get("CODE_INDEXER_DB")
    if raw:
        return Path(raw)
    from code_indexer.utils.config import settings
    return Path(settings.database_url.replace("sqlite:///", ""))


def _engine() -> RetrievalEngine:
    db = _db_path()
    if not db.exists():
        raise FileNotFoundError(
            f"Database not found: {db}\n"
            "Set CODE_INDEXER_DB env var or run: code-indexer index <repo>"
        )
    return RetrievalEngine(db_path=db)


def _read_lines(file_path: str, line_start: Optional[int], line_end: Optional[int]) -> str:
    """Read source lines from disk; return empty string on any error."""
    path = Path(file_path)
    if not path.exists():
        return ""
    try:
        lines = path.read_text(errors="replace").splitlines()
        s = max(0, (line_start or 1) - 1)
        e = line_end if line_end else len(lines)
        return "\n".join(lines[s:e])
    except Exception:
        return ""


# ------------------------------------------------------------------
# Tool: get_context
# ------------------------------------------------------------------

def get_context(query: str, token_budget: int = 6000, language: Optional[str] = None) -> str:
    """Assemble token-budgeted context snippets for a query.

    Returns a markdown-formatted string with file paths, line ranges,
    and the actual source code for each relevant snippet.
    """
    engine = _engine()
    q = RetrievalQuery(
        query=query,
        language_filter=language,
        token_budget=token_budget,
        include_callers=True,
        include_imports=True,
    )
    ctx = engine.get_related_context(q)

    if ctx.is_empty:
        return f"No context found for query: {query!r}"

    lines: list[str] = [
        f"## Context for: {query!r}",
        f"Budget: {token_budget} tokens | Used: {ctx.total_tokens} | Dropped: {ctx.dropped_count}",
        "",
    ]
    for snippet in ctx.snippets:
        header = f"### {snippet.file_path}"
        if snippet.line_start:
            header += f" (lines {snippet.line_start}–{snippet.line_end or snippet.line_start})"
        header += f" — relevance: {snippet.relevance_score:.2f}"
        lines.append(header)

        code = snippet.content or _read_lines(snippet.file_path, snippet.line_start, snippet.line_end)
        if code:
            lines.append(f"```{snippet.language}")
            lines.append(code)
            lines.append("```")
        lines.append("")

    return "\n".join(lines)


# ------------------------------------------------------------------
# Tool: search_symbols
# ------------------------------------------------------------------

def search_symbols(query: str, limit: int = 20) -> str:
    """FTS5 full-text search across symbol names, signatures, and docstrings."""
    engine = _engine()
    results = engine.search_code(query, limit=limit)

    if not results:
        return f"No symbols found for: {query!r}"

    lines = [f"## Symbol search: {query!r}  ({len(results)} results)\n"]
    for s in results:
        sig = f"  `{s.signature}`" if s.signature else ""
        lines.append(f"- **{s.name}** [{s.symbol_type}] — {s.file_path}:{s.line_start}{sig}")
        if s.docstring:
            lines.append(f"  > {s.docstring[:120]}")
    return "\n".join(lines)


# ------------------------------------------------------------------
# Tool: find_symbol
# ------------------------------------------------------------------

def find_symbol(
    name: str,
    symbol_type: Optional[str] = None,
    language: Optional[str] = None,
) -> str:
    """Exact / prefix / substring symbol lookup."""
    engine = _engine()
    types = [symbol_type] if symbol_type else None
    results = engine.find_symbol(name, symbol_types=types, language=language)

    if not results:
        return f"Symbol not found: {name!r}"

    lines = [f"## Symbol: {name!r}  ({len(results)} match(es))\n"]
    for s in results:
        lines.append(f"- **{s.qualified_name or s.name}** [{s.symbol_type}]")
        lines.append(f"  File: {s.file_path}  Lines: {s.line_start}–{s.line_end}")
        if s.signature:
            lines.append(f"  Signature: `{s.signature}`")
        if s.docstring:
            lines.append(f"  Doc: {s.docstring[:120]}")
        lines.append("")
    return "\n".join(lines)


# ------------------------------------------------------------------
# Tool: read_snippet
# ------------------------------------------------------------------

def read_snippet(file_path: str, line_start: int, line_end: int) -> str:
    """Read actual source lines from disk for a given file and line range."""
    code = _read_lines(file_path, line_start, line_end)
    if not code:
        return f"Could not read {file_path} lines {line_start}–{line_end}"
    lang = Path(file_path).suffix.lstrip(".") or "text"
    return f"```{lang}\n{code}\n```"


# ------------------------------------------------------------------
# Tool: get_dependencies
# ------------------------------------------------------------------

def get_dependencies(symbol_id: int, max_depth: int = 2) -> str:
    """Traverse the dependency graph from a symbol (up to max_depth hops)."""
    engine = _engine()
    results = engine.get_dependency_chain(symbol_id, max_depth=max_depth)

    if not results:
        return f"No dependencies found for symbol id={symbol_id}"

    lines = [f"## Dependencies for symbol id={symbol_id}  (depth≤{max_depth})\n"]
    for s in results:
        lines.append(f"- **{s.qualified_name or s.name}** [{s.symbol_type}] — {s.file_path}:{s.line_start}")
    return "\n".join(lines)
