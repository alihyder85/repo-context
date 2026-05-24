# TASKS.md

# Current Milestones

## Phase 1 — Foundation ✅

- [x] Create project structure
- [x] Setup Python environment
- [x] Configure linting and formatting
- [x] Add logging
- [x] Add Docker setup

---

## Phase 2 — Repository Scanner ✅

- [x] Recursive repository scanning
- [x] Ignore pattern support
- [x] File metadata collection
- [x] Incremental file detection
- [x] Scanner tests

---

## Phase 3 — Parser Integration ✅

- [x] Integrate tree-sitter
- [x] Add parser abstraction
- [x] Support Python parsing
- [x] Support Java parsing
- [x] Support JavaScript/TypeScript parsing
- [x] AST traversal utilities
- [x] Parser tests

---

## Phase 4 — Symbol Extraction ✅

- [x] Extract functions
- [x] Extract classes
- [x] Extract imports
- [x] Extract variables
- [x] Store symbol metadata
- [x] ExtractorRegistry (Python, JS, TS, Java)
- [x] Symbol extraction tests

---

## Phase 5 — Reference Graph ✅

- [x] Detect function calls
- [x] Build caller/callee graph
- [x] Detect imports
- [x] Build dependency graph
- [x] Reference tests (covered by extractor tests)

---

## Phase 6 — SQLite Index ✅

- [x] Design DB schema (`indexer/schema.py`)
- [x] Add migrations (`migrate()` in schema.py)
- [x] Create repository/files/symbols/refs tables
- [x] Create reference tables
- [x] Add indexed queries
- [x] `IndexWriter` with full write API
- [x] Indexer tests (16 passing)

---

## Phase 7 — Full Text Search ✅

- [x] Add SQLite FTS5 virtual table
- [x] Index searchable content (name, signature, docstring)
- [x] `rebuild_fts()` in IndexWriter
- [x] FTS search via `RetrievalEngine.search_code()`

---

## Phase 8 — Incremental Reindexing ✅

- [x] Detect dirty files (via ChangeDetector + DB state)
- [x] Reindex modified files only
- [x] Remove deleted files (cascade delete)
- [x] `IncrementalReindexer` with full/incremental modes
- [x] CLI `index` command wired to IncrementalReindexer
- [x] Reindexer tests (9 passing)

---

## Phase 9 — Retrieval Engine ✅

- [x] Symbol lookup APIs (`/api/v1/symbols`)
- [x] FTS search (`/api/v1/symbols/search`)
- [x] Dependency traversal (`/api/v1/symbols/{id}/dependencies`)
- [x] Caller/callee endpoints (`/api/v1/symbols/{id}/references`, `/callers`)
- [x] File listing (`/api/v1/files`)
- [x] Per-file symbols and imports
- [x] Minimal-context builder (`/api/v1/context`)
- [x] Token-aware retrieval
- [x] Retrieval ranking

---

## Phase 10 — Agent APIs ✅

- [x] MCP server (wraps retrieval as Claude tools — direct DB access, no HTTP layer)
- [x] Claude Code skill (slash command `/codebase` for Claude Code CLI)
- [x] `code-indexer mcp` CLI entry point to launch MCP server

---

## Phase 11 — Future Enhancements

- [ ] Embedding search
- [ ] Hybrid retrieval
- [ ] VSCode extension
- [ ] AI summarization cache
