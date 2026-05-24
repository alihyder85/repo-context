"""tree-sitter parser for Python source files."""
from __future__ import annotations

import time
from typing import Any

import tree_sitter_python as tspython
from loguru import logger
from tree_sitter import Language, Parser

from code_indexer.parsers.base import BaseParser
from code_indexer.parsers.models import ParsedFile
from code_indexer.scanner.models import FileMetadata

_LANGUAGE: Language = Language(tspython.language())


class PythonParser(BaseParser):
    """Stateless parser for Python files using tree-sitter."""

    def __init__(self) -> None:
        """Initialise the underlying tree-sitter Parser once."""
        self._parser: Parser = Parser(_LANGUAGE)

    def parse(self, file_meta: FileMetadata) -> ParsedFile:
        """Parse a Python source file.

        Args:
            file_meta: Scanner metadata for the file to parse.

        Returns:
            ParsedFile with tree (partial on syntax error) or error state.
        """
        start = time.perf_counter()
        try:
            source_bytes: bytes = file_meta.absolute_path.read_bytes()
        except Exception as exc:
            logger.warning("PythonParser: cannot read {}: {}", file_meta.absolute_path, exc)
            elapsed = (time.perf_counter() - start) * 1000
            return ParsedFile(
                file_meta=file_meta,
                tree=None,
                language="python",
                source_bytes=None,
                has_errors=True,
                error=str(exc),
                parse_time_ms=elapsed,
            )

        tree: Any = self._parser.parse(source_bytes)
        has_errors: bool = tree.root_node.has_error
        elapsed = (time.perf_counter() - start) * 1000
        if has_errors:
            logger.debug("PythonParser: syntax errors in {}", file_meta.relative_path)
        return ParsedFile(
            file_meta=file_meta,
            tree=tree,
            language="python",
            source_bytes=source_bytes,
            has_errors=has_errors,
            error=None,
            parse_time_ms=elapsed,
        )
