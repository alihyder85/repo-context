# reindex_prompt.md

Read PROJECT.md, ARCHITECTURE.md and TASKS.md before making changes.

Implement Phase 8 — Incremental Reindexing for the AI code indexing system.

Goal:
Build the orchestration layer that ties Phases 2–7 together into a single
runnable pipeline. On first run it indexes the full repo. On subsequent runs
it detects changes (Phase 2) and reindexes only the files that changed —
making the system fast enough to run before every agent query.

---

## Assumptions

Phases 1–7 are complete and available:

| Import | From |
|---|---|
| `RepositoryScanner`, `IncrementalScanner`, `FileMetadata` | `code_indexer.scanner` |
| `ParserRegistry` | `code_indexer.parsers` |
| `ExtractorRegistry` | `code_indexer.extractor` |
| `IndexWriter` | `code_indexer.indexer` |
| `RetrievalEngine` | `code_indexer.retrieval` |
| `IndexerError` | `code_indexer.utils.exceptions` |
| `settings` | `code_indexer.utils.config` |

All four components accept injected dependencies — `IncrementalReindexer`
must receive them via constructor (composition over hard-coding).

---

## Core Requirements

### First Run (Full Index)
1. Create / migrate the database schema
2. Scan the full repository → `ScanResult`
3. Parse + extract every file → `ExtractionResult` per file
4. Write repository record → `repo_id`
5. For each file: write file row, symbols, references
6. Rebuild FTS index once at the end
7. Save scanner state in `IncrementalScanner` for future runs

### Subsequent Runs (Incremental)
1. Scan repo → compare against saved state → `ChangedFiles`
2. **New files**: parse → extract → write (file + symbols + refs)
3. **Modified files**: `delete_file(file_id)` → parse → extract → write fresh
4. **Deleted files**: `delete_file(file_id)` only
5. Rebuild FTS index once at the end (only if any changes occurred)
6. Call `retrieval_engine.invalidate_cache()` after every reindex

### Reindex Stats
Return a `ReindexStats` dataclass after every run:

```python
@dataclass
class ReindexStats:
    files_added: int
    files_updated: int
    files_removed: int
    files_unchanged: int
    symbols_written: int
    references_written: int
    parse_errors: int
    duration_seconds: float
    is_full_index: bool
```

### Error Handling
- A single file failing to parse must NOT abort the whole run
- Collect parse errors in `ReindexStats.parse_errors` and log each one
- DB write errors for a single file: log, skip file, continue
- If the DB itself cannot be opened: raise `IndexerError` immediately

---

## Module Structure

Add to the existing `indexer/` package:

| File | Responsibility |
|---|---|
| `indexer/reindexer.py` | `IncrementalReindexer` orchestrator + `ReindexStats` |

No new packages needed — this is glue code only.

---

## IncrementalReindexer Design

```python
class IncrementalReindexer:
    def __init__(
        self,
        repo_root: Path,
        db_path: Path,
        scanner: Optional[RepositoryScanner] = None,
        parser_registry: Optional[ParserRegistry] = None,
        extractor_registry: Optional[ExtractorRegistry] = None,
        writer: Optional[IndexWriter] = None,
        retrieval_engine: Optional[RetrievalEngine] = None,
    ) -> None: ...

    def run(self) -> ReindexStats:
        """Run a full or incremental reindex depending on DB state."""
        ...

    def full_index(self) -> ReindexStats:
        """Force a full reindex regardless of current state."""
        ...
```

All dependencies default to sensible instances using `settings` — but can be
injected for testing (pass mock writer, mock parser, etc.).

### Processing Pipeline Per File

```
FileMetadata
    ↓
ParserRegistry.parse(file_meta)  →  ParsedFile
    ↓
ExtractorRegistry.extract(parsed_file)  →  ExtractionResult
    ↓
writer.write_file(file_meta, repo_id)  →  file_id
writer.write_symbols(symbols, file_id)  →  symbol_ids
writer.write_references(refs, symbol_id_map)
```

Build a `symbol_id_map: dict[qualified_name, id]` from all symbols across
all files in the batch so cross-file references can be resolved.

---

## CLI Integration

Wire `IncrementalReindexer` into the existing CLI commands in
`code_indexer/cli/main.py`:

```python
@main.command()
@click.argument("repo_path", type=click.Path(exists=True))
@click.option("--full", is_flag=True, help="Force full reindex")
def index(repo_path: str, full: bool) -> None:
    """Index or reindex a repository."""
    reindexer = IncrementalReindexer(
        repo_root=Path(repo_path),
        db_path=Path(settings.database_url.replace("sqlite:///", "")),
    )
    stats = reindexer.full_index() if full else reindexer.run()
    click.echo(f"Indexed  : {stats.files_added} new, {stats.files_updated} updated, "
               f"{stats.files_removed} removed")
    click.echo(f"Symbols  : {stats.symbols_written}")
    click.echo(f"References: {stats.references_written}")
    click.echo(f"Errors   : {stats.parse_errors}")
    click.echo(f"Duration : {stats.duration_seconds:.2f}s")
```

---

## Testing

- Test `full_index()` on a temp repo with known files — assert DB rows match
- Test incremental run with no changes — assert stats show 0 added/updated/removed
- Test incremental run with one new file — assert 1 file_added
- Test incremental run with one modified file — assert 1 file_updated, old symbols deleted
- Test incremental run with one deleted file — assert 1 file_removed, rows cascade deleted
- Test that a parse error on one file does not abort the run
- Test `retrieval_engine.invalidate_cache()` is called after changes
- Test `ReindexStats.is_full_index` is True on first run, False on subsequent
- Integration test: full pipeline from scan → parse → extract → index on this
  repo's own `src/` directory

---

## Generate

1. `indexer/reindexer.py`      — `IncrementalReindexer` + `ReindexStats`
2. Update `indexer/__init__.py` — export `IncrementalReindexer`, `ReindexStats`
3. Update `cli/main.py`         — wire `index` command to `IncrementalReindexer`
4. `tests/test_reindexer.py`   — full test suite
5. Update `tasks.md`           — mark Phase 3–8 complete after successful tests

---

## Constraints

- Follow PROJECT.md and ARCHITECTURE.md
- Strong typing throughout (`from __future__ import annotations`)
- Docstrings on every public class and method
- `reindexer.py` < 250 lines — it is glue, not logic
- All logic lives in its respective layer (scanner/parser/extractor/indexer)
- Full dependency injection — no hard-coded instantiation inside methods
- A single file failure must NEVER abort the pipeline
- FTS rebuild happens ONCE per run at the end, not per file
- `invalidate_cache()` called only when `has_changes` is True
