# retrieval_prompt.md

Read PROJECT.md, ARCHITECTURE.md and TASKS.md before making changes.

Implement the Retrieval Engine module for the AI code indexing system.

Goal:
Build a token-efficient retrieval system that fetches only the most relevant
code context for AI agents instead of entire files or repositories.

The retrieval engine should leverage:
- SQLite structured indexes
- symbol relationships
- dependency graphs
- FTS5 full-text search
- future semantic retrieval support

Core Objectives:
- minimize LLM token usage
- improve retrieval precision
- avoid irrelevant context
- support scalable repository querying

---

## Assumptions

Phases 1–8 are complete. The SQLite index exists with these tables:

```sql
files         (id, repo_id, relative_path, absolute_path, language, size, mtime, hash)
symbols       (id, file_id, name, qualified_name, symbol_type, line_start, line_end, signature, docstring)
              symbol_type IN ('function', 'class', 'method', 'variable', 'import')
symbol_refs   (id, caller_id, callee_id, ref_type)
              ref_type IN ('call', 'import', 'inherit')
symbols_fts   FTS5 virtual table over (name, signature, docstring)
```

The scanner layer exposes `ScannerProtocol` from `code_indexer.scanner.protocols`.
Database access is via a raw sqlite3 connection (no ORM at this layer for speed).

---

## Core Retrieval Features

Implement the following retrieval operations:

- `find_symbol(name)`             — exact + prefix + substring lookup in symbols table
- `find_references(symbol_id)`    — symbols that reference a given symbol
- `find_callers(symbol_id)`       — symbols that call a given symbol
- `find_imports(file_path)`       — all symbols imported by a file
- `search_code(query)`            — FTS5 full-text search across name, signature, docstring
- `get_related_context(query)`    — assemble minimal ContextResult from a RetrievalQuery
- `get_dependency_chain(symbol_id, max_depth)` — multi-hop dependency traversal

The retrieval engine should:
- return minimal relevant context
- support dependency traversal with configurable depth (default: 2)
- deduplicate snippets (same symbol must not appear twice)
- rank by relevance score
- enforce a hard token budget per query

---

## Retrieval Strategy

For a `get_related_context` query:
1. Locate target symbols (FTS5 + exact match)
2. Fetch direct callers / callees (1-hop)
3. Traverse dependency graph up to `max_depth`
4. Score and rank all candidates
5. Fill token budget from highest score downward
6. Return ContextResult (never silently truncate — always report dropped count)

---

## Token Optimization

Implement:
- Configurable token budget per query (default: 8 000 tokens)
- Token estimator: `len(text) // 4` as default; accept any `TokenEstimator` via Protocol
- Expose `remaining_tokens` and `dropped_count` in ContextResult
- Deduplicate identical snippets before budget enforcement

Avoid:
- Returning entire files
- Unrelated dependencies
- Repeated imports / snippets

---

## Ranking

Score each result by:
1. Exact symbol name match: +1.0
2. Prefix match:            +0.7
3. Substring match:         +0.4
4. Direct reference:        +0.5
5. Same file as focal:      +0.3
6. Same directory as focal: +0.1
7. Recently modified:       +0.1  (mtime recency within last 30 days)

Expose `relevance_score` on every result item.
Allow callers to swap in a custom `RankingStrategy` (open/closed principle via Protocol).

---

## Caching

- In-memory LRU cache for repeated symbol lookups (configurable max size, default: 256)
- Invalidate cache when a new index is committed
- Expose `cache_hits` and `cache_misses` counters on the engine

---

## Architecture

Define a `RetrievalProtocol` (mirrors `ScannerProtocol` pattern) so future
AI agent layers depend on an abstraction, not the concrete engine.

Separate concerns strictly:

| Module            | Responsibility                                              |
|-------------------|-------------------------------------------------------------|
| `models.py`       | SymbolResult, FileResult, ContextSnippet, ContextResult, RetrievalQuery |
| `repositories.py` | Raw SQL for symbols, files, references (no logic here)      |
| `ranking.py`      | RelevanceScorer, RankingStrategy Protocol, DefaultRankingStrategy |
| `tokens.py`       | TokenEstimator Protocol + CharDivFourEstimator default      |
| `context.py`      | ContextBuilder: rank → dedup → trim to budget               |
| `engine.py`       | RetrievalEngine orchestrating all of the above + LRU cache  |
| `protocols.py`    | RetrievalProtocol for agent-layer decoupling                |

No raw SQL in `engine.py` — delegate to repositories.
No ranking logic in `repositories.py` — delegate to ranking.

---

## Performance

- FTS5 for all text queries — never use `LIKE '%...%'` on large tables
- Indexed lookups by symbol name, file path, language
- Lazy loading: do not read file content unless the caller requests it
- Batch lookups to minimise round-trips
- Log slow queries (> 100 ms) via loguru

---

## Error Handling

Gracefully handle:
- Missing symbols (return empty list, not an exception)
- Circular dependency traversal (visited-set guard — must never infinite-loop)
- Database connection errors (raise `RetrievalError` from `utils.exceptions`)
- Malformed / empty queries (return empty ContextResult)
- Symbol with no line numbers (snippet content = empty string)

Add structured logging and per-query timing metrics.

---

## Testing

- Unit tests for each repository class using in-memory SQLite (`:memory:`)
- Unit tests for ContextBuilder: budget enforcement, dedup, dropped_count
- Unit tests for RelevanceScorer ranking order
- Unit tests for TokenEstimator
- Integration tests for full `get_related_context` workflow
- Edge cases:
  - Symbol not found
  - Circular dependency (A → B → A) must terminate
  - Query exceeds budget from the very first snippet
  - Empty index (no files, no symbols)
  - FTS5 query with special characters

---

## Generate

1. `models.py`       — all result + query dataclasses
2. `repositories.py` — SymbolRepository, FileRepository, ReferenceRepository
3. `ranking.py`      — RelevanceScorer, RankingStrategy Protocol, DefaultRankingStrategy
4. `tokens.py`       — TokenEstimator Protocol + CharDivFourEstimator
5. `context.py`      — ContextBuilder
6. `engine.py`       — RetrievalEngine with LRU cache
7. `protocols.py`    — RetrievalProtocol
8. `__init__.py`     — clean public API exports
9. `tests/test_retrieval.py` — full test suite
10. `examples.py`    — usage examples showing minimal-context assembly
11. Suggested future improvements (semantic embeddings, reranking, streaming)

---

## Constraints

- Follow PROJECT.md and ARCHITECTURE.md
- Strong typing throughout (use `from __future__ import annotations` for forward refs)
- Docstrings on every public class and method
- Keep modules small (< 200 lines each)
- Design for future AI-agent integrations
- Do NOT re-implement scanning, parsing, or indexing
- Focus only on retrieval, ranking, context assembly, and token budget management
