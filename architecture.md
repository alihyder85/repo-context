# ARCHITECTURE.md

# System Architecture

## High-Level Flow

Repository
↓
Repository Scanner
↓
Tree-sitter Parser
↓
AST Processing
↓
Symbol & Reference Extraction
↓
SQLite + FTS5 Index
↓
Retrieval Engine
↓
Minimal Context Builder
↓
LLM / AI Agent

---

# Components

## 1. Repository Scanner

Responsible for:
- recursive file discovery
- ignore pattern handling
- metadata collection
- incremental change detection

Metadata collected:
- file path
- extension
- size
- mtime
- hash

---

## 2. Parser Layer

Uses tree-sitter to:
- parse source files
- generate ASTs
- support multi-language parsing

Supported initially:
- Python
- Java
- TypeScript
- JavaScript

Parser layer should be extensible.

---

## 3. Symbol Extraction

Extract:
- functions
- methods
- classes
- interfaces
- variables
- imports
- exports

Store:
- symbol type
- location
- scope
- signature

---

## 4. Reference Engine

Build relationships:
- caller → callee
- imports
- inheritance
- type usage

This forms the dependency graph.

---

## 5. SQLite Index

Separate index per repository.

Tables:
- repositories
- files
- symbols
- references
- imports

Use:
- SQLAlchemy
- SQLite FTS5
- indexed queries

---

## 6. Retrieval Engine

Responsible for:
- symbol lookup
- dependency traversal
- full-text search
- minimal-context retrieval

Primary goal:
reduce LLM context size.

---

## 7. Incremental Indexing

Before query:
- detect changed files
- reindex only dirty files
- update references safely

Detection strategy:
- mtime
- file size
- optional hash validation

---

# Architectural Principles

## Local-first

Avoid cloud dependency for indexing/search.

---

## Minimal Context Retrieval

Never send entire repositories to LLMs unnecessarily.

Retrieve:
- target symbols
- direct dependencies
- callers
- nearby context only

---

## Extensibility

Design should support:
- new languages
- vector search
- reranking
- additional storage backends

---

## Separation of Concerns

Each module should be independently testable:
- scanning
- parsing
- indexing
- retrieval
- APIs