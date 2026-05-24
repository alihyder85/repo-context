# agent_prompt.md

Read PROJECT.md, ARCHITECTURE.md and TASKS.md before making changes.

Implement Phase 10 — Agent APIs for the AI code indexing system.

Goal:
Expose the retrieval engine to AI agents via two integration points:
1. An MCP (Model Context Protocol) server that Claude can call as tools
2. A Claude Code slash-command skill (`/codebase`) for the CLI

Both integrations talk directly to the SQLite database via `RetrievalEngine` —
no HTTP layer required, no FastAPI server needs to be running.

---

## Assumptions

Phases 1–9 are complete. The retrieval engine and all its dependencies exist at:
- `code_indexer.retrieval.engine.RetrievalEngine`
- `code_indexer.retrieval.models.RetrievalQuery, SymbolResult, ContextResult`
- `code_indexer.utils.config.settings` (reads `DATABASE_URL` env var)

The database path is resolved from the `DATABASE_URL` setting (strip `sqlite:///` prefix).

---

## Part A — MCP Server

### Location
`src/code_indexer/mcp/`

### Modules

| Module | Responsibility |
|--------|----------------|
| `server.py` | MCP `Server` instance, entry point, stdio transport loop |
| `tools.py` | Tool implementations that call `RetrievalEngine` + read file lines |
| `__init__.py` | Public exports |

### Tools to Expose

```
get_context(query, token_budget=6000, language=None)
    Assemble token-budgeted context for a query. Returns formatted snippets
    with file path, line range, and actual code content.

search_symbols(query, limit=20)
    FTS5 full-text search across symbol names, signatures, docstrings.
    Returns a list of symbol name + file + line + signature.

find_symbol(name, symbol_type=None, language=None)
    Exact / prefix / substring symbol lookup.
    Returns matching symbols with qualified name and location.

read_snippet(file_path, line_start, line_end)
    Read actual source lines from disk for a given file + range.
    Used when Claude wants to inspect code beyond what get_context returns.

get_dependencies(symbol_id, max_depth=2)
    Traverse the dependency graph from a symbol.
    Returns all reachable symbols within max_depth hops.
```

### Tool Response Format

Every tool returns a `list[TextContent]` with a single item containing a
human-readable, markdown-formatted string. This makes it easy for Claude to
read without further parsing.

Example for `get_context`:

```
## Context for: "charge_card"
Budget: 6000 tokens | Used: 2840 | Dropped: 1

### payments/processor.py (lines 3–15) — relevance: 1.00
```python
def charge_card(amount: float, card_token: str) -> bool:
    ...
```

### stripe/charge.py (lines 45–67) — relevance: 0.80
```python
@classmethod
def create(cls, amount, currency, source): ...
```
```

### Configuration

Read the DB path from env var `CODE_INDEXER_DB` (absolute path to `.db` file).
Fall back to `settings.database_url` stripped of `sqlite:///`.
Raise a clear error if the DB file does not exist.

### Entry Point

```bash
code-indexer mcp        # launch MCP server over stdio
```

Add a `mcp` Click command to `src/code_indexer/cli/main.py`.

### MCP Config for Claude Code

Document in a comment at the top of `server.py`:
```json
{
  "mcpServers": {
    "code-indexer": {
      "command": "code-indexer",
      "args": ["mcp"],
      "env": { "CODE_INDEXER_DB": "/path/to/your/index.db" }
    }
  }
}
```

---

## Part B — Claude Code Skill

### Location
`.claude/commands/codebase.md`

### Behaviour

When invoked as `/codebase <query>`:

1. Extract `$ARGUMENTS` (the user's query)
2. Run `code-indexer query "$ARGUMENTS"` via Bash to get context snippets
3. Read the actual source lines for each returned snippet
4. Answer the user's question using only that context
5. Cite file path and line numbers for every claim

### Format

Standard Claude Code custom command markdown — frontmatter with `description`,
then the instructions body referencing `$ARGUMENTS`.

---

## Architecture Rules

- No raw SQL in `tools.py` — use `RetrievalEngine` methods only
- No HTTP calls — MCP server is a direct in-process wrapper
- Each tool call creates a fresh `RetrievalEngine(db_path)` (stateless, safe for concurrent Claude tool calls)
- File reads use `pathlib.Path.read_text(errors="replace")` — never crash on encoding issues
- Gracefully handle: DB not found, symbol not found, file not found, empty results

---

## Testing

`tests/test_mcp.py`:

- Test each tool function directly (not via stdio) using an in-memory-style fixture
  that creates a real temp SQLite DB with minimal seeded data
- Test `get_context` returns formatted markdown with code content
- Test `search_symbols` returns matching symbols
- Test `find_symbol` exact match and no-match cases
- Test `read_snippet` reads correct lines and handles missing file gracefully
- Test `get_dependencies` with a simple A→B→C chain

---

## Generate

1. `src/code_indexer/mcp/__init__.py`
2. `src/code_indexer/mcp/tools.py`
3. `src/code_indexer/mcp/server.py`
4. `.claude/commands/codebase.md`
5. Updated `src/code_indexer/cli/main.py` with `mcp` command
6. Updated `pyproject.toml` — add `mcp>=1.0.0` dependency
7. `tests/test_mcp.py`
8. Updated `tasks.md` — Phase 10 marked ✅

---

## Constraints

- Follow PROJECT.md and ARCHITECTURE.md patterns
- Strong typing throughout (`from __future__ import annotations`)
- Keep `server.py` and `tools.py` under 200 lines each
- Do NOT re-implement retrieval logic — delegate entirely to `RetrievalEngine`
- The MCP server must work with `mcp>=1.0.0` (Anthropic's official Python SDK)
