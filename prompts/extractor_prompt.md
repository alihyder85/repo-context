# extractor_prompt.md

Read PROJECT.md, ARCHITECTURE.md and TASKS.md before making changes.

Implement Phase 4 (Symbol Extraction) and Phase 5 (Reference Graph) for the
AI code indexing system.

Goal:
Build an AST-walking layer that reads `ParsedFile` objects from the parser
(Phase 3) and produces two outputs: a list of `ExtractedSymbol` (definitions)
and a list of `Reference` (usages / calls / imports). Both are consumed by
the indexer (Phase 6).

---

## Assumptions

Phases 1–3 are complete:
- `FileMetadata` from `code_indexer.scanner.models`
- `ParsedFile` from `code_indexer.parsers.models`
- `ExtractorError` exists in `code_indexer.utils.exceptions`
- tree-sitter language packages are installed (from Phase 3)

---

## Why Phase 4 and Phase 5 Are One Prompt

Both phases walk the same AST tree from Phase 3. Walking the tree twice
(once for symbols, once for references) is wasteful. A single pass extracts
both definitions and usages simultaneously. They share the same base
extractor, models, and registry pattern.

---

## Core Requirements

### Symbol Extraction (Phase 4)

Extract the following symbol types from AST nodes:

| Symbol Type | Python example | What to capture |
|---|---|---|
| `function`  | `def foo():` | name, line range, signature, docstring |
| `class`     | `class Foo:` | name, line range, docstring |
| `method`    | `def bar(self):` inside a class | name, parent class, line range, signature |
| `variable`  | module-level `X = 5` | name, line |
| `import`    | `import os`, `from x import y` | imported name, source module |

Rules:
- `qualified_name` = `module.ClassName.method_name` built from nesting context
- `signature` = full first line of the definition (e.g. `def scan(self) -> ScanResult:`)
- `docstring` = first paragraph only (up to first blank line), max 500 chars
- Nested functions ARE extracted (with qualified name showing nesting)
- `__init__`, `__str__` etc. ARE extracted as methods
- Variables only at module scope (not local variables inside functions)

### Reference Extraction (Phase 5)

Extract usages that link symbols together:

| Reference Type | Example | What to capture |
|---|---|---|
| `call`    | `foo()` | caller qualified name → callee name |
| `import`  | `from scanner import RepositoryScanner` | file → imported symbol name + source module |
| `inherit` | `class Foo(Bar):` | child class → parent class name |
| `assign`  | `x = MyClass()` | variable → constructed class name |

Rules:
- `callee_name` is the raw name as written in source — resolution to an ID is
  done by the indexer, not here
- Unresolved / external calls (e.g. `os.path.join`) are still captured
  with `callee_name="os.path.join"` — do not drop them
- One `Reference` per usage site — if `foo()` is called 3 times, emit 3 refs
- `caller_qualified_name` is the qualified name of the enclosing function/method,
  or the file path if at module scope

### Architecture

- `BaseExtractor` ABC — `extract(parsed_file) -> ExtractionResult`
- One concrete class per language: `PythonExtractor`, `JavaScriptExtractor`,
  `JavaExtractor`, `TypeScriptExtractor`
- `ExtractorRegistry` — language → extractor (mirrors `ParserRegistry`)
- `ExtractorProtocol` — `@runtime_checkable Protocol`
- Extractors are stateless — one instance per language, shared across calls

---

## Data Models

```python
@dataclass
class ExtractedSymbol:
    file_path: str                  # relative path (from FileMetadata)
    language: str
    name: str                       # short name (e.g. 'scan')
    qualified_name: str             # full name (e.g. 'scanner.RepositoryScanner.scan')
    symbol_type: str                # 'function'|'class'|'method'|'variable'|'import'
    line_start: int
    line_end: int
    signature: Optional[str]        # first line of definition
    docstring: Optional[str]        # first paragraph of docstring


@dataclass
class Reference:
    file_path: str                  # file where the usage occurs
    caller_qualified_name: str      # qualified name of enclosing scope
    callee_name: str                # raw name as written (unresolved)
    ref_type: str                   # 'call'|'import'|'inherit'|'assign'
    line: int                       # line where the usage occurs


@dataclass
class ExtractionResult:
    file_meta: FileMetadata
    symbols: list[ExtractedSymbol]
    references: list[Reference]
    has_errors: bool
    error: Optional[str]
    extract_time_ms: float
```

---

## Module Structure

| File | Responsibility |
|---|---|
| `extractor/models.py`      | `ExtractedSymbol`, `Reference`, `ExtractionResult` |
| `extractor/base.py`        | `BaseExtractor` ABC |
| `extractor/python.py`      | `PythonExtractor` — walks Python AST nodes |
| `extractor/javascript.py`  | `JavaScriptExtractor` |
| `extractor/typescript.py`  | `TypeScriptExtractor` |
| `extractor/java.py`        | `JavaExtractor` |
| `extractor/registry.py`    | `ExtractorRegistry` |
| `extractor/protocols.py`   | `ExtractorProtocol` |
| `extractor/__init__.py`    | clean public exports |

---

## Tree-sitter Node Walking Pattern

Use this pattern for all extractors:

```python
def _walk(self, node, source_bytes: bytes, context: ExtractionContext) -> None:
    """Recursively walk AST nodes."""
    if node.type == "function_definition":
        self._extract_function(node, source_bytes, context)
    elif node.type == "class_definition":
        self._extract_class(node, source_bytes, context)
    # ... etc
    for child in node.children:
        self._walk(child, source_bytes, context)
```

Helper to get node text:
```python
def _node_text(node, source_bytes: bytes) -> str:
    return source_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="replace")
```

---

## Testing

- Unit test each extractor against a real code snippet (use `tmp_path` + real file)
- Test Python extractor: function, class, method, import, nested function
- Test Python extractor: `from x import y as z` (alias handling)
- Test reference extraction: function call, import, inheritance
- Test `ExtractionResult` on a file with syntax errors (must return partial results)
- Test `ExtractorRegistry` dispatch to correct extractor
- Integration test: full pipeline `FileMetadata → parse → extract` for a real `.py` file
- Edge cases:
  - empty file
  - file with no symbols (only comments)
  - deeply nested class/function (qualified name must be correct)
  - `__all__` exports (capture as variables)

---

## Generate

1. `extractor/models.py`     — `ExtractedSymbol`, `Reference`, `ExtractionResult`
2. `extractor/base.py`       — `BaseExtractor` ABC + `ExtractionContext` helper
3. `extractor/python.py`     — `PythonExtractor`
4. `extractor/javascript.py` — `JavaScriptExtractor`
5. `extractor/typescript.py` — `TypeScriptExtractor`
6. `extractor/java.py`       — `JavaExtractor`
7. `extractor/registry.py`   — `ExtractorRegistry`
8. `extractor/protocols.py`  — `ExtractorProtocol`
9. `extractor/__init__.py`   — public exports
10. `tests/test_extractor.py` — full test suite
11. `extractor/examples.py`  — usage examples

---

## Constraints

- Follow PROJECT.md and ARCHITECTURE.md
- Strong typing throughout (`from __future__ import annotations`)
- Docstrings on every public class and method
- Each module < 200 lines
- Do NOT parse files — consume `ParsedFile` from Phase 3
- Do NOT write to the database — that is Phase 6
- Do NOT resolve callee names to IDs — that is Phase 6
- Extractors must be stateless and thread-safe
- Return empty `ExtractionResult` on failure — never raise from `extract()`
