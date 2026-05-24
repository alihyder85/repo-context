# indexer_prompt.md

Read PROJECT.md, ARCHITECTURE.md and TASKS.md before making changes.

Implement Phase 6 (SQLite Index) and Phase 7 (Full Text Search) for the
AI code indexing system.

Goal:
Build the persistence layer that writes `ExtractedSymbol` and `Reference`
objects from the extractor (Phase 4+5) into a structured SQLite database with
FTS5 full-text search. This database is the single source of truth consumed
by the Retrieval Engine (Phase 9).

---

## Assumptions

Phases 1–5 are complete:
- `FileMetadata` from `code_indexer.scanner.models`
- `ExtractedSymbol`, `Reference`, `ExtractionResult` from `code_indexer.extractor.models`
- `DatabaseError` exists in `code_indexer.utils.exceptions`
- `settings.database_url` contains the SQLite path (e.g. `sqlite:///data/index.db`)
- The retrieval layer (Phase 9) already reads from this schema — do NOT change
  column names or table names below

---

## Why Phase 6 and Phase 7 Are One Prompt

FTS5 is a `CREATE VIRTUAL TABLE` in the same migration file as the main schema.
The `IndexWriter` rebuilds the FTS index in the same transaction as bulk writes.
They are inseparable at the implementation level.

---

## Database Schema (authoritative — retrieval layer depends on this exactly)

```sql
-- Track schema version for migrations
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);

-- One row per repository being indexed
CREATE TABLE IF NOT EXISTS repositories (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    root_path   TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

-- One row per source file
CREATE TABLE IF NOT EXISTS files (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_id       INTEGER NOT NULL REFERENCES repositories(id),
    relative_path TEXT NOT NULL,
    absolute_path TEXT NOT NULL,
    language      TEXT NOT NULL,
    size          INTEGER NOT NULL DEFAULT 0,
    mtime         TEXT NOT NULL DEFAULT '',
    hash          TEXT,
    UNIQUE(repo_id, relative_path)
);

-- One row per extracted symbol (function, class, method, variable, import)
CREATE TABLE IF NOT EXISTS symbols (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id        INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    name           TEXT NOT NULL,
    qualified_name TEXT,
    symbol_type    TEXT NOT NULL,
    line_start     INTEGER,
    line_end       INTEGER,
    signature      TEXT,
    docstring      TEXT
);

-- One row per reference (call, import, inherit, assign)
CREATE TABLE IF NOT EXISTS symbol_refs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    caller_id  INTEGER REFERENCES symbols(id) ON DELETE CASCADE,
    callee_id  INTEGER REFERENCES symbols(id) ON DELETE SET NULL,
    callee_name TEXT NOT NULL,
    ref_type   TEXT NOT NULL,
    line       INTEGER
);

-- Indexes for fast retrieval queries
CREATE INDEX IF NOT EXISTS idx_symbols_name     ON symbols(name);
CREATE INDEX IF NOT EXISTS idx_symbols_file_id  ON symbols(file_id);
CREATE INDEX IF NOT EXISTS idx_symbols_type     ON symbols(symbol_type);
CREATE INDEX IF NOT EXISTS idx_refs_caller      ON symbol_refs(caller_id);
CREATE INDEX IF NOT EXISTS idx_refs_callee      ON symbol_refs(callee_id);
CREATE INDEX IF NOT EXISTS idx_files_language   ON files(language);
CREATE INDEX IF NOT EXISTS idx_files_repo       ON files(repo_id);

-- FTS5 virtual table for full-text search across symbol names, signatures, docstrings
CREATE VIRTUAL TABLE IF NOT EXISTS symbols_fts USING fts5(
    name,
    signature,
    docstring,
    content=symbols,
    content_rowid=id
);
```

**Current schema version: 1**

---

## Core Requirements

### Schema Management
- `schema.py` owns all DDL — no SQL in other files
- `create_tables(conn)` — idempotent, safe to call on existing DB
- `migrate(conn)` — reads `schema_version`, applies missing migrations in order
- Migration 1 = initial schema above
- Each migration is a plain SQL string in a list — simple, no Alembic

### IndexWriter (the main write API)
- `write_repository(repo_root, name) -> int` — upsert repository row, return repo_id
- `write_file(file_meta, repo_id) -> int` — upsert file row, return file_id
- `write_symbols(symbols, file_id) -> list[int]` — bulk insert, return symbol IDs
- `write_references(refs, symbol_id_map) -> None` — resolve callee names → IDs using
  `symbol_id_map: dict[qualified_name, id]`, insert rows with `callee_id=NULL` for unresolved
- `delete_file(file_id) -> None` — delete file + cascade to symbols + refs
- `rebuild_fts() -> None` — `INSERT INTO symbols_fts(symbols_fts) VALUES('rebuild')`
- All writes wrapped in explicit transactions — one transaction per file

### Connection Management
- `IndexWriter` owns a single `sqlite3.Connection` for its lifetime
- Caller controls open/close (context manager support: `__enter__` / `__exit__`)
- Enable WAL mode on open: `PRAGMA journal_mode=WAL`
- Enable foreign keys: `PRAGMA foreign_keys=ON`

---

## Module Structure

| File | Responsibility |
|---|---|
| `indexer/schema.py`   | DDL strings, `create_tables()`, `migrate()` |
| `indexer/writer.py`   | `IndexWriter` — all write operations |
| `indexer/models.py`   | `RepositoryRecord`, `FileRecord` row dataclasses |
| `indexer/protocols.py`| `IndexerProtocol` |
| `indexer/__init__.py` | clean public exports |

---

## IndexerProtocol

```python
@runtime_checkable
class IndexerProtocol(Protocol):
    def write_repository(self, repo_root: str, name: str) -> int: ...
    def write_file(self, file_meta: FileMetadata, repo_id: int) -> int: ...
    def write_symbols(self, symbols: list[ExtractedSymbol], file_id: int) -> list[int]: ...
    def write_references(self, refs: list[Reference], symbol_id_map: dict[str, int]) -> None: ...
    def delete_file(self, file_id: int) -> None: ...
    def rebuild_fts(self) -> None: ...
```

---

## Performance

- Use `executemany` for bulk symbol and reference inserts — never insert one row at a time
- One transaction per file (not one per symbol)
- WAL mode enabled — allows concurrent reads from the retrieval engine while writing
- FTS rebuild called once after all files in a batch are written — not after each file

---

## Testing

Use in-memory SQLite (`:memory:`) for all tests.

- Test `create_tables()` is idempotent (call twice, no error)
- Test `migrate()` advances schema_version correctly
- Test `write_repository()` upserts correctly (second call updates, not duplicate)
- Test `write_file()` upserts correctly
- Test `write_symbols()` returns correct IDs
- Test `write_references()` resolves known callee names, leaves NULL for unknown
- Test `delete_file()` cascades to symbols and refs
- Test `rebuild_fts()` does not raise
- Integration test: write a full `ExtractionResult` through the writer, then query
  the symbols table and assert rows match
- Edge cases:
  - file with zero symbols
  - reference to symbol in another file (cross-file callee resolution)
  - duplicate file write (upsert must not create duplicate rows)
  - very long docstring (> 500 chars — should be stored truncated or as-is)

---

## Generate

1. `indexer/schema.py`    — DDL, `create_tables()`, `migrate()`
2. `indexer/writer.py`    — `IndexWriter`
3. `indexer/models.py`    — `RepositoryRecord`, `FileRecord`
4. `indexer/protocols.py` — `IndexerProtocol`
5. `indexer/__init__.py`  — public exports
6. `tests/test_indexer.py` — full test suite
7. `indexer/examples.py`  — usage examples showing full write pipeline

---

## Constraints

- Follow PROJECT.md and ARCHITECTURE.md
- Strong typing throughout (`from __future__ import annotations`)
- Docstrings on every public class and method
- Each module < 200 lines
- Schema column names and table names must EXACTLY match what the retrieval
  layer (Phase 9) already queries — do not rename anything
- Do NOT parse files — consume `ExtractionResult` from Phase 4+5
- Do NOT implement scanning or symbol extraction
- Use raw `sqlite3` — no SQLAlchemy ORM at this layer (speed requirement)
- WAL mode and foreign keys must be enabled on every connection
