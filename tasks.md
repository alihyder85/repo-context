# TASKS.md

# Current Milestones

## Phase 1 — Foundation

- [ ] Create project structure
- [ ] Setup Python environment
- [ ] Configure linting and formatting
- [ ] Add logging
- [ ] Add Docker setup

---

## Phase 2 — Repository Scanner

- [ ] Recursive repository scanning
- [ ] Ignore pattern support
- [ ] File metadata collection
- [ ] Incremental file detection
- [ ] Scanner tests

---

## Phase 3 — Parser Integration

- [ ] Integrate tree-sitter
- [ ] Add parser abstraction
- [ ] Support Python parsing
- [ ] Support Java parsing
- [ ] AST traversal utilities
- [ ] Parser tests

---

## Phase 4 — Symbol Extraction

- [ ] Extract functions
- [ ] Extract classes
- [ ] Extract imports
- [ ] Extract variables
- [ ] Store symbol metadata
- [ ] Symbol extraction tests

---

## Phase 5 — Reference Graph

- [ ] Detect function calls
- [ ] Build caller/callee graph
- [ ] Detect imports
- [ ] Build dependency graph
- [ ] Reference tests

---

## Phase 6 — SQLite Index

- [ ] Design DB schema
- [ ] Add migrations
- [ ] Create repository tables
- [ ] Create symbol tables
- [ ] Create reference tables
- [ ] Add indexed queries

---

## Phase 7 — Full Text Search

- [ ] Add SQLite FTS5
- [ ] Index searchable content
- [ ] Add search ranking
- [ ] Add snippet retrieval

---

## Phase 8 — Incremental Reindexing

- [ ] Detect dirty files
- [ ] Reindex modified files only
- [ ] Remove deleted files
- [ ] Benchmark indexing speed

---

## Phase 9 — Retrieval Engine

- [ ] Symbol lookup APIs
- [ ] Dependency traversal
- [ ] Minimal-context builder
- [ ] Token-aware retrieval
- [ ] Retrieval ranking

---

## Phase 10 — Future Enhancements

- [ ] Embedding search
- [ ] Hybrid retrieval
- [ ] Agent APIs
- [ ] VSCode integration
- [ ] AI summarization cache