"""tree-sitter parser for JavaScript source files."""
from __future__ import annotations

import time
from typing import Any

import tree_sitter_javascript as tsjavascript
from loguru import logger
from tree_sitter import Language, Parser

from code_indexer.parsers.base import BaseParser
from code_indexer.parsers.models import ParsedFile
from code_indexer.scanner.models import FileMetadata

_LANGUAGE: Language = Language(tsjavascript.language())


class JavaScriptParser(BaseParser):
    """Stateless parser for JavaScript / JSX files using tree-sitter."""

    def __init__(self) -> None:
        """Initialise the underlying tree-sitter Parser once."""
        self._parser: Parser = Parser(_LANGUAGE)

    def parse(self, file_meta: FileMetadata) -> ParsedFile:
        """Parse a JavaScript source file.

        Args:
            file_meta: Scanner metadata for the file to parse.

        Returns:
            ParsedFile with tree (partial on syntax error) or error state.
        """
        start = time.perf_counter()
        try:
            source_bytes: bytes = file_meta.absolute_path.read_bytes()
        except Exception as exc:
            logger.warning("JavaScriptParser: cannot read {}: {}", file_meta.absolute_path, exc)
            elapsed = (time.perf_counter() - start) * 1000
            return ParsedFile(
                file_meta=file_meta,
                tree=None,
                language="javascript",
                source_bytes=None,
                has_errors=True,
                error=str(exc),
                parse_time_ms=elapsed,
            )

        tree: Any = self._parser.parse(source_bytes)
        has_errors: bool = tree.root_node.has_error
        elapsed = (time.perf_counter() - start) * 1000
        return ParsedFile(
            file_meta=file_meta,
            tree=tree,
            language="javascript",
            source_bytes=source_bytes,
            has_errors=has_errors,
            error=None,
            parse_time_ms=elapsed,
        )
