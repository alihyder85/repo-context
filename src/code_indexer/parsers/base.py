"""Abstract base class for language parsers."""
from __future__ import annotations

from abc import ABC, abstractmethod

from code_indexer.parsers.models import ParsedFile
from code_indexer.scanner.models import FileMetadata


class BaseParser(ABC):
    """ABC for stateless, thread-safe language parsers.

    A single instance is created at startup and reused for every file of
    that language.  Implementations must never raise — all errors are
    surfaced through ``ParsedFile.error``.
    """

    @abstractmethod
    def parse(self, file_meta: FileMetadata) -> ParsedFile:
        """Parse *file_meta* and return a ``ParsedFile``.

        Args:
            file_meta: Scanner metadata for the file to parse.

        Returns:
            ``ParsedFile`` — never raises; errors go into ``.error``.
        """
