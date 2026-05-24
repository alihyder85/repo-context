"""Data models for the extractor layer."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from code_indexer.scanner.models import FileMetadata


@dataclass
class ExtractedSymbol:
    """A single named symbol extracted from a source file.

    Attributes:
        file_path: Relative path of the file (from FileMetadata).
        language: Programming language of the file.
        name: Short name (e.g. ``scan``).
        qualified_name: Fully qualified name (e.g. ``scanner.RepositoryScanner.scan``).
        symbol_type: One of ``function``, ``class``, ``method``, ``variable``, ``import``.
        line_start: First line of the definition (1-based).
        line_end: Last line of the definition (1-based).
        signature: First line of the definition text.
        docstring: First paragraph of docstring, max 500 chars.
    """

    file_path: str
    language: str
    name: str
    qualified_name: str
    symbol_type: str
    line_start: int
    line_end: int
    signature: Optional[str] = None
    docstring: Optional[str] = None


@dataclass
class Reference:
    """A usage that links one symbol to another.

    Attributes:
        file_path: File where the usage occurs.
        caller_qualified_name: Qualified name of the enclosing scope.
        callee_name: Raw name as written in source (unresolved).
        ref_type: One of ``call``, ``import``, ``inherit``, ``assign``.
        line: Line number of the usage (1-based).
    """

    file_path: str
    caller_qualified_name: str
    callee_name: str
    ref_type: str
    line: int


@dataclass
class ExtractionResult:
    """Aggregated extraction output for a single file.

    Attributes:
        file_meta: Original scanner metadata.
        symbols: All extracted symbols.
        references: All extracted references.
        has_errors: True if extraction encountered errors.
        error: Human-readable error message.
        extract_time_ms: Wall-clock extraction time in milliseconds.
    """

    file_meta: FileMetadata
    symbols: list[ExtractedSymbol] = field(default_factory=list)
    references: list[Reference] = field(default_factory=list)
    has_errors: bool = False
    error: Optional[str] = None
    extract_time_ms: float = 0.0
