"""Data models for the parser layer."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from code_indexer.scanner.models import FileMetadata


@dataclass
class ParsedFile:
    """Result of parsing a source file into an AST.

    Attributes:
        file_meta: Original metadata from the scanner.
        tree: tree-sitter Tree object, or None on read/language error.
        language: Language string (e.g. 'python').
        source_bytes: Raw file bytes needed by the extractor.
        has_errors: True if tree-sitter detected syntax errors.
        error: Human-readable error message when parsing failed.
        parse_time_ms: Wall-clock time to parse in milliseconds.
    """

    file_meta: FileMetadata
    tree: Optional[Any]
    language: str
    source_bytes: Optional[bytes]
    has_errors: bool
    error: Optional[str]
    parse_time_ms: float
