# parser_prompt.md

Read PROJECT.md, ARCHITECTURE.md and TASKS.md before making changes.

Implement Phase 3 — Parser Integration for the AI code indexing system.

Goal:
Build a production-grade, language-agnostic parsing layer that reads source
files and produces structured AST output consumed by the extractor (Phase 4).
The parser must never crash on bad input — graceful degradation is mandatory.

---

## Assumptions

Phases 1–2 are complete:
- `FileMetadata` is available from `code_indexer.scanner.models`
- `ScanResult` delivers `list[FileMetadata]` to this layer
- `ParserError` exception exists in `code_indexer.utils.exceptions`
- tree-sitter is listed in pyproject.toml dependencies

Add the following to pyproject.toml dependencies:
```
"tree-sitter-python>=0.21.0",
"tree-sitter-javascript>=0.21.0",
"tree-sitter-java>=0.21.0",
"tree-sitter-typescript>=0.21.0",
```

Use the modern tree-sitter API (>=0.20):
```python
import tree_sitter_python as tspython
from tree_sitter import Language, Parser
PY_LANGUAGE = Language(tspython.language())
parser = Parser(PY_LANGUAGE)
```

---

## Core Requirements

### Parsing
- Parse source files into tree-sitter AST trees
- Support Python, JavaScript, TypeScript, Java initially
- Language detected from `FileMetadata.language` — no guessing from extension
- Read file bytes (not text) — tree-sitter works on bytes
- Return structured `ParsedFile` for every input (never raise on bad syntax)

### Error Handling
- Syntax errors: return `ParsedFile` with `has_errors=True`, include partial tree
- File read errors (permission, encoding): return `ParsedFile` with `error` message, `tree=None`
- Unsupported language: return `ParsedFile` with `error="unsupported language"`, `tree=None`
- Log all errors via loguru — never silently discard

### Architecture
- `BaseParser` ABC — one method: `parse(file_meta: FileMetadata) -> ParsedFile`
- One concrete parser class per language: `PythonParser`, `JavaScriptParser`, `JavaParser`, `TypeScriptParser`
- `ParserRegistry` — maps language string → parser instance (config-driven dict, not if/else)
- `ParserProtocol` — `@runtime_checkable Protocol` mirroring `ScannerProtocol` pattern
- All parsers are **stateless** — safe to share a single instance across threads
- Parser instances created once in registry, reused for all files of that language

### Performance
- Parsers are instantiated once at startup — not per file
- File reads are buffered (use `file_path.read_bytes()`)
- No concurrency inside the parser layer — threading handled by the caller

---

## Data Models

```python
@dataclass
class ParsedFile:
    file_meta: FileMetadata        # original metadata from scanner
    tree: Optional[Any]            # tree-sitter Tree object (None on read error)
    language: str                  # language string (e.g. 'python')
    source_bytes: Optional[bytes]  # raw file bytes (needed by extractor for node text)
    has_errors: bool               # True if tree-sitter detected syntax errors
    error: Optional[str]           # human-readable error message if parse failed
    parse_time_ms: float           # time taken to parse in milliseconds
```

---

## Module Structure

| File | Responsibility |
|---|---|
| `parsers/models.py` | `ParsedFile` dataclass |
| `parsers/base.py` | `BaseParser` ABC |
| `parsers/python.py` | `PythonParser` |
| `parsers/javascript.py` | `JavaScriptParser` (handles `.js` and `.jsx`) |
| `parsers/typescript.py` | `TypeScriptParser` (handles `.ts` and `.tsx`) |
| `parsers/java.py` | `JavaParser` |
| `parsers/registry.py` | `ParserRegistry` — language → parser mapping |
| `parsers/protocols.py` | `ParserProtocol` |
| `parsers/__init__.py` | clean public exports |

---

## ParserRegistry Design

```python
class ParserRegistry:
    def get(self, language: str) -> Optional[BaseParser]: ...
    def supported_languages(self) -> list[str]: ...
    def parse(self, file_meta: FileMetadata) -> ParsedFile: ...
    # parse() is the main entry point — handles unsupported language gracefully
```

Registry is built once with all supported parsers. Adding a new language = one
dict entry + one new parser class. No changes to existing code.

---

## Testing

- Unit test each parser with valid source in that language
- Unit test each parser with intentionally broken syntax (must not raise)
- Unit test each parser with an unreadable file path (must not raise)
- Unit test `ParserRegistry` with unsupported language (must return error ParsedFile)
- Unit test `ParserRegistry.parse()` dispatches to correct parser
- Integration test: feed a real `ScanResult` through the registry, assert all
  files produce a `ParsedFile` with no uncaught exceptions
- Edge cases:
  - empty file (0 bytes)
  - file with only comments
  - binary file accidentally passed in
  - very large file (> 1MB)

---

## Generate

1. `parsers/models.py`     — `ParsedFile` dataclass
2. `parsers/base.py`       — `BaseParser` ABC
3. `parsers/python.py`     — `PythonParser`
4. `parsers/javascript.py` — `JavaScriptParser`
5. `parsers/typescript.py` — `TypeScriptParser`
6. `parsers/java.py`       — `JavaParser`
7. `parsers/registry.py`   — `ParserRegistry`
8. `parsers/protocols.py`  — `ParserProtocol`
9. `parsers/__init__.py`   — public exports
10. `tests/test_parsers.py` — full test suite
11. `parsers/examples.py`  — usage examples
12. Update `pyproject.toml` — add tree-sitter language packages

---

## Constraints

- Follow PROJECT.md and ARCHITECTURE.md
- Strong typing throughout (`from __future__ import annotations`)
- Docstrings on every public class and method
- Each module < 150 lines
- Do NOT extract symbols or references — that is Phase 4+5
- Do NOT write to the database — that is Phase 6
- Do NOT implement concurrency — caller handles threading
- Parsers must be stateless and thread-safe
