"""File filtering and ignore pattern handling."""

import fnmatch
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional


class FileFilter(ABC):
    """Abstract base class for file filters."""

    @abstractmethod
    def should_include(self, path: Path) -> bool:
        """Determine if a file should be included.

        Args:
            path: File path to check

        Returns:
            True if file should be included, False otherwise
        """
        pass


class IgnorePatternFilter(FileFilter):
    """Filter files based on ignore patterns.

    Supports:
    - Glob patterns (e.g., '*.pyc', '__pycache__/*')
    - Directory prefixes (e.g., '.git/')
    - Exact matches
    """

    def __init__(self, patterns: list[str]) -> None:
        """Initialize filter with patterns.

        Args:
            patterns: List of glob patterns to ignore
        """
        self.patterns = patterns
        self.directory_patterns = [p for p in patterns if p.endswith("/")]
        self.file_patterns = [p for p in patterns if not p.endswith("/")]

    def should_include(self, path: Path) -> bool:
        """Check if path matches any ignore pattern.

        Args:
            path: File or directory path

        Returns:
            True if path should be included (doesn't match any pattern)
        """
        path_str = str(path)
        parts = path.parts

        # Check directory patterns against each component of the path so that
        # wildcard patterns like '*.egg-info/' are matched correctly.
        for pattern in self.directory_patterns:
            dir_pattern = pattern.rstrip("/")
            if any(fnmatch.fnmatch(part, dir_pattern) for part in parts):
                return False

        # Check file patterns
        for pattern in self.file_patterns:
            if fnmatch.fnmatch(path.name, pattern) or fnmatch.fnmatch(
                path_str, pattern
            ):
                return False

        return True


class HiddenFileFilter(FileFilter):
    """Filter out hidden and system files.

    When a repo_root is provided, only the path components relative to the
    repo root are checked, so parent directories outside the repository
    (e.g. /home/user/.myrepo/) do not incorrectly exclude all files.
    """

    def __init__(self, repo_root: Optional[Path] = None) -> None:
        """Initialize hidden file filter.

        Args:
            repo_root: Repository root path. When provided, only path
                components relative to this root are checked for hidden
                prefixes.
        """
        self.repo_root = repo_root

    def should_include(self, path: Path) -> bool:
        """Check if path contains hidden components.

        Args:
            path: File or directory path

        Returns:
            True if path has no hidden components within the repo
        """
        check_path = path.relative_to(self.repo_root) if self.repo_root else path
        for part in check_path.parts:
            if part.startswith(".") and part not in (".", ".."):
                return False
        return True


class SizeFilter(FileFilter):
    """Filter files based on size limits."""

    def __init__(self, max_size_bytes: int) -> None:
        """Initialize size filter.

        Args:
            max_size_bytes: Maximum file size in bytes
        """
        self.max_size_bytes = max_size_bytes

    def should_include(self, path: Path) -> bool:
        """Check if file is within size limit.

        Args:
            path: File path to check

        Returns:
            True if file is within size limit
        """
        try:
            return path.stat().st_size <= self.max_size_bytes
        except (OSError, IOError):
            return False


class LanguageFilter(FileFilter):
    """Filter files by supported programming languages."""

    def __init__(self, supported_extensions: set[str]) -> None:
        """Initialize language filter.

        Args:
            supported_extensions: Set of supported file extensions (e.g., {'.py', '.java'})
        """
        self.supported_extensions = supported_extensions

    def should_include(self, path: Path) -> bool:
        """Check if file has supported extension.

        Args:
            path: File path to check

        Returns:
            True if file extension is supported
        """
        return path.suffix.lower() in self.supported_extensions


class CompositeFilter(FileFilter):
    """Combine multiple filters (all must pass)."""

    def __init__(self, filters: list[FileFilter]) -> None:
        """Initialize with list of filters.

        Args:
            filters: List of FileFilter instances
        """
        self.filters = filters

    def should_include(self, path: Path) -> bool:
        """Check if path passes all filters.

        Args:
            path: File path to check

        Returns:
            True if all filters return True
        """
        return all(f.should_include(path) for f in self.filters)

    def add_filter(self, filter: FileFilter) -> None:
        """Add a filter to the chain.

        Args:
            filter: FileFilter instance to add
        """
        self.filters.append(filter)


class FilterChain:
    """Easy builder for creating filter chains."""

    def __init__(self) -> None:
        """Initialize empty filter chain."""
        self.filters: list[FileFilter] = []

    def with_ignore_patterns(self, patterns: list[str]) -> "FilterChain":
        """Add ignore pattern filter.

        Args:
            patterns: List of glob patterns to ignore

        Returns:
            Self for chaining
        """
        self.filters.append(IgnorePatternFilter(patterns))
        return self

    def with_hidden_files(
        self, exclude: bool = True, repo_root: Optional[Path] = None
    ) -> "FilterChain":
        """Add hidden file filter.

        Args:
            exclude: Whether to exclude hidden files
            repo_root: Repository root so only repo-relative components are
                checked (avoids false positives when the repo lives under a
                hidden directory such as /home/user/.myrepo/).

        Returns:
            Self for chaining
        """
        if exclude:
            self.filters.append(HiddenFileFilter(repo_root=repo_root))
        return self

    def with_size_limit(self, max_size_mb: int) -> "FilterChain":
        """Add size filter.

        Args:
            max_size_mb: Maximum file size in MB

        Returns:
            Self for chaining
        """
        max_bytes = max_size_mb * 1024 * 1024
        self.filters.append(SizeFilter(max_bytes))
        return self

    def with_languages(self, extensions: set[str]) -> "FilterChain":
        """Add language filter.

        Args:
            extensions: Set of supported extensions

        Returns:
            Self for chaining
        """
        self.filters.append(LanguageFilter(extensions))
        return self

    def build(self) -> CompositeFilter:
        """Build the filter chain.

        Returns:
            CompositeFilter combining all filters
        """
        return CompositeFilter(self.filters)
