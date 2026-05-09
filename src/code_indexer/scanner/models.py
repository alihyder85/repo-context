"""Data models for file metadata and scanning."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class FileMetadata:
    """Metadata for a scanned file.

    Attributes:
        absolute_path: Absolute path to the file
        relative_path: Relative path from repository root
        extension: File extension (e.g., '.py', '.java')
        size: File size in bytes
        mtime: Last modification time
        language: Detected programming language
        hash: Optional SHA256 hash for validation
    """

    absolute_path: Path
    relative_path: Path
    extension: str
    size: int
    mtime: datetime
    language: str
    hash: Optional[str] = None

    def __hash__(self) -> int:
        """Make FileMetadata hashable."""
        return hash(self.absolute_path)

    def __eq__(self, other: object) -> bool:
        """Compare FileMetadata by path."""
        if not isinstance(other, FileMetadata):
            return NotImplemented
        return self.absolute_path == other.absolute_path

    def to_dict(self) -> dict:
        """Serialize to a plain dictionary for SQLite storage.

        Returns a flat dict with JSON-safe types so the indexer layer
        can persist this metadata without importing the model class.

        Returns:
            Dictionary representation of this file's metadata
        """
        return {
            "absolute_path": str(self.absolute_path),
            "relative_path": str(self.relative_path),
            "extension": self.extension,
            "size": self.size,
            "mtime": self.mtime.isoformat(),
            "language": self.language,
            "hash": self.hash,
        }

    @classmethod
    def from_path(
        cls,
        absolute_path: Path,
        repo_root: Path,
        language_mapping: dict[str, str],
    ) -> "FileMetadata":
        """Create FileMetadata from a file path.

        Args:
            absolute_path: Absolute path to the file
            repo_root: Repository root path
            language_mapping: Mapping of extensions to languages

        Returns:
            FileMetadata instance
        """
        stat = absolute_path.stat()
        relative_path = absolute_path.relative_to(repo_root)
        extension = absolute_path.suffix.lower()
        language = language_mapping.get(extension, "unknown")

        return cls(
            absolute_path=absolute_path,
            relative_path=relative_path,
            extension=extension,
            size=stat.st_size,
            mtime=datetime.fromtimestamp(stat.st_mtime),
            language=language,
        )


@dataclass
class ScanResult:
    """Result of a repository scan.

    Attributes:
        files: List of scanned file metadata
        total_files: Total number of files scanned
        total_size: Total size of all files in bytes
        scan_time: Time taken to scan in seconds
        errors: List of errors encountered during scan
    """

    files: list[FileMetadata]
    total_files: int
    total_size: int
    scan_time: float
    errors: list[str]

    @property
    def has_errors(self) -> bool:
        """Check if there were any errors during scan."""
        return len(self.errors) > 0


@dataclass
class RepositoryIndex:
    """Index of repository files tracking state.

    Attributes:
        repo_root: Repository root path
        files: Mapping of relative path to metadata
        last_scan_time: Last scan timestamp
    """

    repo_root: Path
    files: dict[Path, FileMetadata]
    last_scan_time: Optional[datetime] = None

    def get_file(self, relative_path: Path) -> Optional[FileMetadata]:
        """Get file metadata by relative path."""
        return self.files.get(relative_path)

    def get_by_absolute_path(self, absolute_path: Path) -> Optional[FileMetadata]:
        """Get file metadata by absolute path."""
        for file_meta in self.files.values():
            if file_meta.absolute_path == absolute_path:
                return file_meta
        return None

    def update_from_scan(self, scan_result: ScanResult) -> None:
        """Update index with scan results."""
        # Replace all files
        self.files = {file.relative_path: file for file in scan_result.files}
        self.last_scan_time = datetime.now()


@dataclass
class ChangedFiles:
    """Represents changes detected in repository.

    Attributes:
        new_files: Files that are new
        modified_files: Files that were modified
        deleted_files: Files that were deleted
    """

    new_files: list[FileMetadata]
    modified_files: list[FileMetadata]
    deleted_files: list[FileMetadata]

    @property
    def has_changes(self) -> bool:
        """Check if there are any changes."""
        return bool(self.new_files or self.modified_files or self.deleted_files)

    @property
    def total_changed(self) -> int:
        """Get total number of changed files."""
        return len(self.new_files) + len(self.modified_files) + len(self.deleted_files)
