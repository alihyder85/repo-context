"""Runtime-checkable Protocol for parser implementations."""
from __future__ import annotations

from typing import runtime_checkable

from typing import Protocol

from code_indexer.parsers.models import ParsedFile
from code_indexer.scanner.models import FileMetadata


@runtime_checkable
class ParserProtocol(Protocol):
    """Structural interface that any parser must satisfy."""

    def parse(self, file_meta: FileMetadata) -> ParsedFile:
        """Parse a source file into a ParsedFile."""
        ...
