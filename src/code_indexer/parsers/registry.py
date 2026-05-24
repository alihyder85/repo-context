"""Language-to-parser registry."""
from __future__ import annotations

from typing import Optional

from loguru import logger

from code_indexer.parsers.base import BaseParser
from code_indexer.parsers.java import JavaParser
from code_indexer.parsers.javascript import JavaScriptParser
from code_indexer.parsers.models import ParsedFile
from code_indexer.parsers.python import PythonParser
from code_indexer.parsers.typescript import TypeScriptParser
from code_indexer.scanner.models import FileMetadata


class ParserRegistry:
    """Map language strings to stateless parser instances.

    Parsers are created once at construction time and reused for every
    file of that language.  Adding a new language requires only adding a
    dict entry — no existing code changes.
    """

    def __init__(self) -> None:
        """Build the default language → parser mapping."""
        self._parsers: dict[str, BaseParser] = {
            "python": PythonParser(),
            "javascript": JavaScriptParser(),
            "typescript": TypeScriptParser(),
            "java": JavaParser(),
        }

    def get(self, language: str) -> Optional[BaseParser]:
        """Return the parser for *language*, or None if unsupported.

        Args:
            language: Language string from FileMetadata.

        Returns:
            Parser instance or None.
        """
        return self._parsers.get(language)

    def supported_languages(self) -> list[str]:
        """Return all supported language strings.

        Returns:
            Sorted list of supported language identifiers.
        """
        return sorted(self._parsers.keys())

    def parse(self, file_meta: FileMetadata) -> ParsedFile:
        """Dispatch to the correct parser or return an error ParsedFile.

        This is the main entry point.  Unsupported languages are handled
        gracefully — no exception is raised.

        Args:
            file_meta: Scanner metadata for the file to parse.

        Returns:
            ParsedFile — never raises.
        """
        parser = self._parsers.get(file_meta.language)
        if parser is None:
            logger.debug("ParserRegistry: unsupported language '{}'", file_meta.language)
            return ParsedFile(
                file_meta=file_meta,
                tree=None,
                language=file_meta.language,
                source_bytes=None,
                has_errors=False,
                error=f"unsupported language: {file_meta.language}",
                parse_time_ms=0.0,
            )
        return parser.parse(file_meta)
