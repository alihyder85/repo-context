"""Language-to-extractor registry."""
from __future__ import annotations

from typing import Optional

from loguru import logger

from code_indexer.extractor.base import BaseExtractor
from code_indexer.extractor.java import JavaExtractor
from code_indexer.extractor.javascript import JavaScriptExtractor
from code_indexer.extractor.models import ExtractionResult
from code_indexer.extractor.python import PythonExtractor
from code_indexer.extractor.typescript import TypeScriptExtractor
from code_indexer.parsers.models import ParsedFile
from code_indexer.scanner.models import FileMetadata


class ExtractorRegistry:
    """Map language strings to stateless extractor instances.

    Extractors are created once at construction time and reused for every
    file of that language.
    """

    def __init__(self) -> None:
        """Build the default language → extractor mapping."""
        self._extractors: dict[str, BaseExtractor] = {
            "python": PythonExtractor(),
            "javascript": JavaScriptExtractor(),
            "typescript": TypeScriptExtractor(),
            "java": JavaExtractor(),
        }

    def get(self, language: str) -> Optional[BaseExtractor]:
        """Return the extractor for *language*, or None if unsupported.

        Args:
            language: Language string from FileMetadata.

        Returns:
            Extractor instance or None.
        """
        return self._extractors.get(language)

    def supported_languages(self) -> list[str]:
        """Return all supported language strings."""
        return sorted(self._extractors.keys())

    def extract(self, parsed_file: ParsedFile) -> ExtractionResult:
        """Dispatch to the correct extractor or return an empty ExtractionResult.

        Unsupported languages are handled gracefully — no exception raised.

        Args:
            parsed_file: Parser output for the file.

        Returns:
            ExtractionResult — never raises.
        """
        extractor = self._extractors.get(parsed_file.language)
        if extractor is None:
            logger.debug(
                "ExtractorRegistry: unsupported language '{}'", parsed_file.language
            )
            return ExtractionResult(
                file_meta=parsed_file.file_meta,
                has_errors=False,
                error=f"unsupported language: {parsed_file.language}",
            )
        return extractor.extract(parsed_file)
