# AI Code Indexing & Token Optimization System

A local-first code intelligence system that indexes any repository and exposes a retrieval API that gives AI agents only the most relevant code context — reducing token usage by up to 93%.

## How it works

```
Your Repo
    │
    ▼
Scanner → Parser → Extractor → SQLite (symbols + refs + FTS5)
                                    │
                          ┌─────────┴──────────┐
                          ▼                    ▼
                    REST API              MCP Server
                 (FastAPI/uvicorn)   (Claude tools, stdio)
                          │                    │
                          └─────────┬──────────┘
                                    ▼
                              Claude / AI Agent
                         (receives only relevant snippets)
```

## Features

| Feature | Status |
|---------|--------|
| Repository scanning with ignore patterns | ✅ |
| AST parsing (Python, JS, TS, Java) via tree-sitter | ✅ |
| Symbol extraction (functions, classes, methods, variables, imports) | ✅ |
| Dependency & call-graph building | ✅ |
| SQLite index with FTS5 full-text search | ✅ |
| Incremental reindexing (only changed files) | ✅ |
| Token-budgeted retrieval with relevance ranking | ✅ |
| FastAPI REST API | ✅ |
| MCP server (Claude tool integration) | ✅ |
| Claude Code `/codebase` skill | ✅ |
| Docker support | ✅ |

---

## Quick Start

### 1. Install

```bash
git clone <repository-url>
cd repo-context

python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

pip install -e .
code-indexer --version
```

### 2. Configure

```bash
cp .env.example .env
```

Edit `.env`:
```
DATABASE_URL=sqlite:///data/index.db
LOG_LEVEL=INFO
MAX_FILE_SIZE_MB=10
```

### 3. Index a repository

```bash
# First-time full index
code-indexer index /path/to/your/repo

# Subsequent runs — only changed files are reindexed
code-indexer index /path/to/your/repo

# Force full reindex
code-indexer index /path/to/your/repo --full
```

Output:
```
Indexed  : 142 new, 0 updated, 0 removed, 0 unchanged
Symbols  : 1847
Refs     : 3204
Errors   : 0
Duration : 4.21s
```

### 4. Query from the CLI

```bash
code-indexer query "charge_card" --budget 4000
```

### 5. Start the REST API

```bash
code-indexer serve --host 0.0.0.0 --port 8000
# Swagger UI → http://localhost:8000/docs
```

---

## MCP Server (Claude Integration)

The MCP server lets Claude call your index as tools directly — no manual copy-pasting, no HTTP server needed in the loop.

### Setup

Add to `~/.claude.json` (Claude Code) or your MCP client config:

```json
{
  "mcpServers": {
    "code-indexer": {
      "command": "code-indexer",
      "args": ["mcp"],
      "env": { "CODE_INDEXER_DB": "/absolute/path/to/data/index.db" }
    }
  }
}
```

Restart Claude Code. Claude now has these tools:

| Tool | What it does |
|------|-------------|
| `get_context` | Fetch token-budgeted snippets for a query (main tool) |
| `search_symbols` | FTS5 search across names, signatures, docstrings |
| `find_symbol` | Exact / prefix lookup by symbol name |
| `read_snippet` | Read raw source lines from a file |
| `get_dependencies` | Traverse dependency graph from a symbol |

Claude picks the right tool automatically. You just ask questions normally:

> "How does `charge_card` work and what does it call?"

Claude calls `get_context("charge_card")` → gets ranked snippets → answers with citations.

### Launch manually

```bash
# With env var
CODE_INDEXER_DB=/path/to/index.db code-indexer mcp

# With --db flag
code-indexer mcp --db /path/to/index.db
```

---

## Claude Code Skill

A `/codebase` slash command for Claude Code CLI that retrieves context before answering:

```
/codebase how does the incremental reindexer detect changed files?
```

The skill runs `code-indexer query` under the hood, reads the returned file lines, and answers using only retrieved context with file:line citations.

The skill file lives at [.claude/commands/codebase.md](.claude/commands/codebase.md).

---

## REST API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/health` | Health check |
| GET | `/api/v1/context` | **Main endpoint** — token-budgeted context for a query |
| GET | `/api/v1/symbols` | Search symbols by name |
| GET | `/api/v1/symbols/search` | FTS5 full-text search |
| GET | `/api/v1/symbols/{id}` | Get symbol by ID |
| GET | `/api/v1/symbols/{id}/references` | Symbols called by this symbol |
| GET | `/api/v1/symbols/{id}/callers` | Symbols that call this symbol |
| GET | `/api/v1/symbols/{id}/dependencies` | Dependency graph traversal |
| GET | `/api/v1/files` | List indexed files |
| GET | `/api/v1/files/{id}` | Get file by ID |
| GET | `/api/v1/files/{id}/symbols` | Symbols defined in a file |
| GET | `/api/v1/files/{id}/imports` | Imports for a file |

Full interactive docs at `http://localhost:8000/docs`.

### Context endpoint example

```bash
curl "http://localhost:8000/api/v1/context?q=charge_card&token_budget=4000"
```

```json
{
  "query": "charge_card",
  "total_tokens": 840,
  "budget_tokens": 4000,
  "remaining_tokens": 3160,
  "dropped_count": 0,
  "snippets": [
    {
      "file_path": "payments/processor.py",
      "symbol_name": "charge_card",
      "line_start": 3,
      "line_end": 15,
      "relevance_score": 1.0,
      "token_estimate": 420
    }
  ]
}
```

---

## Python API

```python
from code_indexer.retrieval import RetrievalEngine, RetrievalQuery
from pathlib import Path

engine = RetrievalEngine(Path("data/index.db"))

context = engine.get_related_context(
    RetrievalQuery(
        query="charge_card",
        token_budget=4_000,
        max_depth=2,
        include_callers=True,
        include_imports=True,
    )
)

for snippet in context.snippets:
    print(f"{snippet.file_path}:{snippet.line_start}  score={snippet.relevance_score:.2f}")

print(f"Used {context.total_tokens} tokens, dropped {context.dropped_count} snippets")
```

---

## Docker

```bash
cd docker
docker-compose up --build
```

---

## Project Structure

```
src/code_indexer/
├── scanner/       # Repository scanning, ignore patterns, change detection
├── parsers/       # Tree-sitter parsers (Python, JS, TS, Java)
├── extractor/     # Symbol + reference extraction from ASTs
├── indexer/       # SQLite schema, IndexWriter, IncrementalReindexer
├── retrieval/     # RetrievalEngine, ranking, token budgeting, FTS
├── api/           # FastAPI routes (symbols, files, context, health)
├── mcp/           # MCP server — tools.py + server.py
├── cli/           # Click CLI (scan, index, query, serve, mcp)
└── utils/         # Config, logging, exceptions

tests/             # 125 tests across all modules
prompts/           # Phase-by-phase build prompts
.claude/commands/  # Claude Code skills
docker/            # Docker + docker-compose
```

---

## CLI Reference

```bash
code-indexer scan   <repo_path>                    # discover files
code-indexer index  <repo_path> [--full] [--db]    # index or reindex
code-indexer query  <query>     [--budget] [--db]  # retrieve context
code-indexer serve  [--host] [--port]              # start REST API
code-indexer mcp    [--db]                         # start MCP server
```

---

## Testing

```bash
pytest                          # 125 tests
pytest tests/test_mcp.py -v     # MCP tools only
pytest --cov=src/code_indexer   # with coverage
```

---

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///code_indexer.db` | SQLite path |
| `CODE_INDEXER_DB` | — | Override for MCP server |
| `LOG_LEVEL` | `INFO` | Logging verbosity |
| `MAX_FILE_SIZE_MB` | `10` | Skip files larger than this |
| `IGNORE_PATTERNS` | `.git, __pycache__, node_modules, .venv` | Scan exclusions |
| `API_HOST` | `0.0.0.0` | FastAPI bind host |
| `API_PORT` | `8000` | FastAPI bind port |

---

## License

[MIT License](LICENSE)
