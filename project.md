# PROJECT.md

# AI Code Indexing & Token Optimization System

## Goal

Build a local-first code intelligence system that helps AI coding agents reduce token usage by retrieving only the most relevant code context from repositories.

The system should:
- parse repositories into structured ASTs
- extract symbols and references
- build dependency relationships
- store searchable metadata in SQLite
- provide fast retrieval APIs
- minimize LLM context size

---

## Core Objectives

1. Reduce unnecessary LLM token usage
2. Avoid repeatedly sending entire files to LLMs
3. Build repository-aware retrieval
4. Support incremental indexing
5. Provide symbol-level code understanding
6. Enable fast local querying
7. Support future AI coding agents

---

## Core Features

- Repository scanning
- Tree-sitter parsing
- AST generation
- Symbol extraction
- Reference extraction
- Dependency graph generation
- SQLite storage
- FTS5 full-text search
- Incremental reindexing
- Minimal-context retrieval
- Semantic search (future)
- Agent APIs (future)

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python |
| Parsing | tree-sitter |
| Database | SQLite |
| Search | SQLite FTS5 |
| API | FastAPI |
| ORM | SQLAlchemy |

---

## Design Principles

- Local-first architecture
- Minimal token usage
- Fast retrieval
- Extensible parser system
- Modular architecture
- Repository isolation
- Incremental updates
- AI-agent friendly

---

## Future Goals

- Embedding-based semantic search
- VSCode extension
- Multi-repo indexing
- Distributed indexing
- AI summarization cache
- Retrieval ranking engine
- Agent tool integrations