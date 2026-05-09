"""Incremental change detection for repositories."""

import hashlib
from pathlib import Path
from typing import Optional

from loguru import logger

from code_indexer.scanner.models import (
    ChangedFiles,
    FileMetadata,
    RepositoryIndex,
    ScanResult,
)
from code_indexer.utils.exceptions import ScannerError


class ChangeDetector:
    """Detect changes in repository files."""

    def __init__(self, use_hash: bool = False) -> None:
        """Initialize change detector.

        Args:
            use_hash: Whether to use SHA256 hash for validation (slower but more accurate)
        """
        self.use_hash = use_hash

    def detect_changes(
        self,
        current_index: RepositoryIndex,
        new_scan: ScanResult,
    ) -> ChangedFiles:
        """Detect changes between current index and new scan.

        Args:
            current_index: Current repository index
            new_scan: New scan results

        Returns:
            ChangedFiles containing new, modified, and deleted files
        """
        new_files = []
        modified_files = []
        deleted_files = []

        # Index new scan results by relative path
        new_files_by_path = {file.relative_path: file for file in new_scan.files}

        # Check for new and modified files
        for rel_path, new_file in new_files_by_path.items():
            old_file = current_index.get_file(rel_path)

            if old_file is None:
                # New file
                new_files.append(new_file)
            elif self._has_changed(old_file, new_file):
                # Modified file
                modified_files.append(new_file)

        # Check for deleted files
        for rel_path, old_file in current_index.files.items():
            if rel_path not in new_files_by_path:
                deleted_files.append(old_file)

        logger.info(
            f"Detected changes: {len(new_files)} new, {len(modified_files)} modified, {len(deleted_files)} deleted"
        )

        return ChangedFiles(
            new_files=new_files,
            modified_files=modified_files,
            deleted_files=deleted_files,
        )

    def _has_changed(self, old_file: FileMetadata, new_file: FileMetadata) -> bool:
        """Determine if a file has changed.

        Args:
            old_file: Previous file metadata
            new_file: New file metadata

        Returns:
            True if file has changed
        """
        # Quick check: size or mtime changed
        if old_file.size != new_file.size or old_file.mtime != new_file.mtime:
            # If using hash, validate with hash
            if self.use_hash:
                return self._compare_hashes(old_file, new_file)
            return True

        return False

    def _compare_hashes(self, old_file: FileMetadata, new_file: FileMetadata) -> bool:
        """Compare file hashes.

        Args:
            old_file: Previous file metadata
            new_file: New file metadata

        Returns:
            True if hashes differ
        """
        old_hash = old_file.hash or self._compute_hash(old_file.absolute_path)
        new_hash = new_file.hash or self._compute_hash(new_file.absolute_path)
        return old_hash != new_hash

    @staticmethod
    def _compute_hash(file_path: Path, chunk_size: int = 8192) -> str:
        """Compute SHA256 hash of a file.

        Args:
            file_path: Path to file
            chunk_size: Size of chunks to read

        Returns:
            Hex digest of SHA256 hash
        """
        sha256_hash = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(chunk_size), b""):
                    sha256_hash.update(chunk)
            return sha256_hash.hexdigest()
        except (IOError, OSError) as e:
            logger.error(f"Failed to compute hash for {file_path}: {e}")
            raise ScannerError(f"Failed to compute hash: {e}")


class IncrementalScanner:
    """Scanner that tracks incremental changes.

    Dependencies are injected to keep this class composable and testable.
    Pass a custom ``change_detector`` or ``initial_index`` to override the
    defaults — for example, to resume from a previously persisted index or
    to swap in a test double.
    """

    def __init__(
        self,
        repo_root: Path,
        use_hash: bool = False,
        change_detector: Optional[ChangeDetector] = None,
        initial_index: Optional[RepositoryIndex] = None,
    ) -> None:
        """Initialize incremental scanner.

        Args:
            repo_root: Repository root path
            use_hash: Whether to use hashes for change validation.
                Ignored when ``change_detector`` is provided explicitly.
            change_detector: Optional pre-configured ChangeDetector to use.
                Defaults to ``ChangeDetector(use_hash=use_hash)``.
            initial_index: Optional pre-populated RepositoryIndex to resume
                from. Defaults to an empty index.
        """
        self.repo_root = repo_root
        self.change_detector = change_detector or ChangeDetector(use_hash=use_hash)
        self.index = initial_index or RepositoryIndex(repo_root=repo_root, files={})

    def update_index(self, scan_result: ScanResult) -> ChangedFiles:
        """Update index with new scan and detect changes.

        Args:
            scan_result: New scan results

        Returns:
            ChangedFiles containing the differences
        """
        if not self.index.files:
            # First scan - all files are new
            changes = ChangedFiles(
                new_files=scan_result.files,
                modified_files=[],
                deleted_files=[],
            )
        else:
            # Incremental scan
            changes = self.change_detector.detect_changes(self.index, scan_result)

        # Update index
        self.index.update_from_scan(scan_result)

        return changes

    def get_index(self) -> RepositoryIndex:
        """Get current repository index.

        Returns:
            Current RepositoryIndex
        """
        return self.index
