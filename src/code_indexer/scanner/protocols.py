"""Protocols (interfaces) for the scanner layer.

These allow the parser and indexer layers to depend on abstractions
rather than on the concrete RepositoryScanner, keeping modules decoupled
as the system grows through Phases 3–9.
"""

from pathlib import Path
from typing import Protocol, runtime_checkable

from code_indexer.scanner.models import FileMetadata, ScanResult


@runtime_checkable
class ScannerProtocol(Protocol):
    """Interface the parser and indexer layers use to consume scan results.

    Any object that exposes these methods is a valid scanner — whether it is
    RepositoryScanner, a cached replay scanner used in tests, or a future
    remote scanner.
    """

    def scan(self) -> ScanResult:
        """Scan the full repository and return file metadata.

        Returns:
            ScanResult containing discovered files and statistics
        """
        ...

    def scan_directory(self, directory: Path) -> ScanResult:
        """Scan a specific sub-directory within the repository.

        Args:
            directory: Directory path relative to the repository root

        Returns:
            ScanResult for the given directory
        """
        ...

    def get_files_by_language(
        self, scan_result: ScanResult, language: str
    ) -> list[FileMetadata]:
        """Return only files matching a given language.

        Args:
            scan_result: Scan result to filter
            language: Language name (e.g. 'python', 'java')

        Returns:
            Filtered list of FileMetadata
        """
        ...

    def get_files_by_extension(
        self, scan_result: ScanResult, extension: str
    ) -> list[FileMetadata]:
        """Return only files matching a given extension.

        Args:
            scan_result: Scan result to filter
            extension: File extension including dot (e.g. '.py')

        Returns:
            Filtered list of FileMetadata
        """
        ...

    def get_statistics(self, scan_result: ScanResult) -> dict:
        """Return aggregate statistics for a scan result.

        Args:
            scan_result: Scan result to analyse

        Returns:
            Dictionary of statistics (counts, sizes, language distribution)
        """
        ...
