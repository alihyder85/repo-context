"""Repository scanner for code indexing."""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

from loguru import logger

from code_indexer.scanner.filters import CompositeFilter, FilterChain
from code_indexer.scanner.models import FileMetadata, ScanResult
from code_indexer.utils.exceptions import ScannerError

# Default language mapping (extension -> language)
DEFAULT_LANGUAGE_MAPPING = {
    ".py": "python",
    ".java": "java",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".c": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".h": "c",
    ".hpp": "cpp",
    ".cs": "csharp",
    ".rb": "ruby",
    ".php": "php",
    ".swift": "swift",
    ".kt": "kotlin",
    ".scala": "scala",
    ".sql": "sql",
    ".html": "html",
    ".css": "css",
    ".scss": "scss",
    ".less": "less",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".xml": "xml",
    ".toml": "toml",
}

# Default ignore patterns
DEFAULT_IGNORE_PATTERNS = [
    ".git/",
    ".gitignore",
    ".github/",
    "__pycache__/",
    "*.pyc",
    "*.pyo",
    ".pytest_cache/",
    ".mypy_cache/",
    "node_modules/",
    "package-lock.json",
    "yarn.lock",
    "dist/",
    "build/",
    "target/",
    ".venv/",
    "venv/",
    "env/",
    ".eggs/",
    "*.egg-info/",
    ".DS_Store",
    "Thumbs.db",
    ".idea/",
    ".vscode/",
]


class RepositoryScanner:
    """Scan repositories and collect file metadata."""

    def __init__(
        self,
        repo_root: Path,
        language_mapping: Optional[dict[str, str]] = None,
        ignore_patterns: Optional[list[str]] = None,
        max_file_size_mb: int = 10,
        use_threading: bool = True,
        max_workers: int = 4,
    ) -> None:
        """Initialize repository scanner.

        Args:
            repo_root: Root directory of repository
            language_mapping: Mapping of extensions to languages
            ignore_patterns: List of patterns to ignore
            max_file_size_mb: Maximum file size in MB
            use_threading: Whether to use threading for scanning
            max_workers: Number of worker threads
        """
        self.repo_root = Path(repo_root).resolve()
        if not self.repo_root.is_dir():
            raise ScannerError(f"Repository root is not a directory: {self.repo_root}")

        self.language_mapping = {**DEFAULT_LANGUAGE_MAPPING, **(language_mapping or {})}
        self.ignore_patterns = ignore_patterns or DEFAULT_IGNORE_PATTERNS
        self.max_file_size_mb = max_file_size_mb
        self.use_threading = use_threading
        self.max_workers = max_workers

        # Build filter chain
        self.filter = self._build_filter_chain()

        logger.info(f"Initialized scanner for {self.repo_root}")

    def _build_filter_chain(self) -> CompositeFilter:
        """Build the filter chain from configuration.

        Returns:
            CompositeFilter combining all filters
        """
        supported_extensions = set(self.language_mapping.keys())

        return (
            FilterChain()
            .with_ignore_patterns(self.ignore_patterns)
            .with_hidden_files(exclude=True, repo_root=self.repo_root)
            .with_size_limit(self.max_file_size_mb)
            .with_languages(supported_extensions)
            .build()
        )

    def scan(self) -> ScanResult:
        """Scan repository and collect file metadata.

        Returns:
            ScanResult containing scanned files and statistics

        Raises:
            ScannerError: If scanning fails
        """
        logger.info(f"Starting repository scan: {self.repo_root}")
        start_time = time.time()
        errors: list[str] = []
        files: list[FileMetadata] = []

        try:
            if self.use_threading:
                files, errors = self._scan_threaded()
            else:
                files, errors = self._scan_sequential()
        except Exception as e:
            logger.error(f"Scanning error: {e}")
            raise ScannerError(f"Repository scan failed: {e}") from e

        elapsed_time = time.time() - start_time
        total_size = sum(f.size for f in files)

        result = ScanResult(
            files=files,
            total_files=len(files),
            total_size=total_size,
            scan_time=elapsed_time,
            errors=errors,
        )

        logger.info(
            f"Scan completed: {result.total_files} files, {result.total_size / 1024 / 1024:.2f}MB in {result.scan_time:.2f}s"
        )

        return result

    def _scan_sequential(self) -> tuple[list[FileMetadata], list[str]]:
        """Scan repository sequentially.

        Returns:
            Tuple of (file metadata list, error messages list)
        """
        files: list[FileMetadata] = []
        errors: list[str] = []
        for file_path in self.repo_root.rglob("*"):
            if self._should_process(file_path):
                try:
                    file_meta = FileMetadata.from_path(
                        file_path,
                        self.repo_root,
                        self.language_mapping,
                    )
                    files.append(file_meta)
                except (OSError, IOError) as e:
                    msg = f"Error processing {file_path}: {e}"
                    logger.warning(msg)
                    errors.append(msg)

        return files, errors

    def _scan_threaded(self) -> tuple[list[FileMetadata], list[str]]:
        """Scan repository using thread pool.

        Returns:
            Tuple of (file metadata list, error messages list)
        """
        files: list[FileMetadata] = []
        errors: list[str] = []
        file_paths = [p for p in self.repo_root.rglob("*") if self._should_process(p)]

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(self._process_file, file_path): file_path
                for file_path in file_paths
            }

            for future in as_completed(futures):
                try:
                    file_meta = future.result()
                    if file_meta:
                        files.append(file_meta)
                except Exception as e:
                    file_path = futures[future]
                    msg = f"Error processing {file_path}: {e}"
                    logger.warning(msg)
                    errors.append(msg)

        return files, errors

    def _should_process(self, path: Path) -> bool:
        """Check if path should be processed.

        Args:
            path: Path to check

        Returns:
            True if path should be processed
        """
        # Only process files, not directories
        if not path.is_file():
            return False

        # Apply filters
        return self.filter.should_include(path)

    def _process_file(self, file_path: Path) -> Optional[FileMetadata]:
        """Process a single file.

        Args:
            file_path: Path to the file

        Returns:
            FileMetadata or None if processing fails
        """
        try:
            return FileMetadata.from_path(
                file_path,
                self.repo_root,
                self.language_mapping,
            )
        except (OSError, IOError) as e:
            logger.warning(f"Error processing {file_path}: {e}")
            return None

    def scan_directory(self, directory: Path) -> ScanResult:
        """Scan a specific directory within the repository.

        Args:
            directory: Directory to scan (relative to repo root)

        Returns:
            ScanResult for the directory

        Raises:
            ScannerError: If directory doesn't exist
        """
        target_dir = self.repo_root / directory
        if not target_dir.is_dir():
            raise ScannerError(f"Directory not found: {target_dir}")

        logger.info(f"Scanning directory: {target_dir}")
        start_time = time.time()
        files: list[FileMetadata] = []
        errors: list[str] = []

        if self.use_threading:
            file_paths = [p for p in target_dir.rglob("*") if self._should_process(p)]
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {
                    executor.submit(self._process_file, fp): fp for fp in file_paths
                }
                for future in as_completed(futures):
                    try:
                        file_meta = future.result()
                        if file_meta:
                            files.append(file_meta)
                    except Exception as e:
                        msg = f"Error processing {futures[future]}: {e}"
                        logger.warning(msg)
                        errors.append(msg)
        else:
            for file_path in target_dir.rglob("*"):
                if self._should_process(file_path):
                    try:
                        file_meta = FileMetadata.from_path(
                            file_path,
                            self.repo_root,
                            self.language_mapping,
                        )
                        files.append(file_meta)
                    except (OSError, IOError) as e:
                        msg = f"Error processing {file_path}: {e}"
                        logger.warning(msg)
                        errors.append(msg)

        total_size = sum(f.size for f in files)

        return ScanResult(
            files=files,
            total_files=len(files),
            total_size=total_size,
            scan_time=time.time() - start_time,
            errors=errors,
        )

    def get_files_by_language(
        self, scan_result: ScanResult, language: str
    ) -> list[FileMetadata]:
        """Get files of specific language from scan result.

        Args:
            scan_result: ScanResult to filter
            language: Language to filter by

        Returns:
            List of FileMetadata for the language
        """
        return [f for f in scan_result.files if f.language == language]

    def get_files_by_extension(
        self, scan_result: ScanResult, extension: str
    ) -> list[FileMetadata]:
        """Get files of specific extension from scan result.

        Args:
            scan_result: ScanResult to filter
            extension: Extension to filter by (e.g., '.py')

        Returns:
            List of FileMetadata for the extension
        """
        ext = extension if extension.startswith(".") else f".{extension}"
        return [f for f in scan_result.files if f.extension == ext]

    def get_statistics(self, scan_result: ScanResult) -> dict:
        """Get statistics from scan result.

        Args:
            scan_result: ScanResult to analyze

        Returns:
            Dictionary of statistics
        """
        language_counts: dict[str, int] = {}
        for file_meta in scan_result.files:
            language_counts[file_meta.language] = (
                language_counts.get(file_meta.language, 0) + 1
            )

        return {
            "total_files": scan_result.total_files,
            "total_size_bytes": scan_result.total_size,
            "total_size_mb": scan_result.total_size / 1024 / 1024,
            "scan_time_seconds": scan_result.scan_time,
            "files_per_second": (
                scan_result.total_files / scan_result.scan_time
                if scan_result.scan_time > 0
                else 0
            ),
            "language_distribution": language_counts,
            "error_count": len(scan_result.errors),
        }
