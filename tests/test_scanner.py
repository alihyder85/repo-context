"""Tests for the repository scanner module."""

from datetime import datetime
from pathlib import Path

import pytest

from code_indexer.scanner.filters import (
    CompositeFilter,
    FilterChain,
    HiddenFileFilter,
    IgnorePatternFilter,
    LanguageFilter,
    SizeFilter,
)
from code_indexer.scanner.incremental import ChangeDetector
from code_indexer.scanner.models import (
    FileMetadata,
    RepositoryIndex,
    ScanResult,
)
from code_indexer.scanner.scanner import RepositoryScanner
from code_indexer.utils.exceptions import ScannerError


class TestFileMetadata:
    """Tests for FileMetadata model."""

    def test_from_path(self, tmp_path: Path) -> None:
        """Test creating FileMetadata from a file path."""
        # Create a test file
        test_file = tmp_path / "test.py"
        test_file.write_text("print('hello')")

        language_mapping = {".py": "python"}
        file_meta = FileMetadata.from_path(test_file, tmp_path, language_mapping)

        assert file_meta.extension == ".py"
        assert file_meta.language == "python"
        assert file_meta.size > 0
        assert file_meta.relative_path == Path("test.py")

    def test_hashable(self, tmp_path: Path) -> None:
        """Test that FileMetadata is hashable."""
        test_file = tmp_path / "test.py"
        test_file.write_text("test")

        file_meta1 = FileMetadata.from_path(test_file, tmp_path, {".py": "python"})
        file_meta2 = FileMetadata.from_path(test_file, tmp_path, {".py": "python"})

        # Should be able to use in set
        files_set = {file_meta1, file_meta2}
        assert len(files_set) == 1


class TestIgnorePatternFilter:
    """Tests for IgnorePatternFilter."""

    def test_ignore_glob_patterns(self) -> None:
        """Test ignoring files by glob pattern."""
        filter = IgnorePatternFilter(["*.pyc", "*.pyo"])

        assert not filter.should_include(Path("test.pyc"))
        assert not filter.should_include(Path("test.pyo"))
        assert filter.should_include(Path("test.py"))

    def test_ignore_directories(self) -> None:
        """Test ignoring directories."""
        filter = IgnorePatternFilter([".git/", "__pycache__/"])

        assert not filter.should_include(Path(".git/config"))
        assert not filter.should_include(Path("src/__pycache__/test.pyc"))
        assert filter.should_include(Path("src/test.py"))

    def test_ignore_exact_matches(self) -> None:
        """Test ignoring exact file matches."""
        filter = IgnorePatternFilter(["*.gitignore", "package-lock.json"])

        assert not filter.should_include(Path(".gitignore"))
        assert not filter.should_include(Path("package-lock.json"))
        assert filter.should_include(Path("test.txt"))


class TestHiddenFileFilter:
    """Tests for HiddenFileFilter."""

    def test_exclude_hidden_files(self) -> None:
        """Test excluding hidden files."""
        filter = HiddenFileFilter()

        assert not filter.should_include(Path(".git/config"))
        assert not filter.should_include(Path(".env"))
        assert filter.should_include(Path("test.py"))
        assert filter.should_include(Path("src/test.py"))


class TestSizeFilter:
    """Tests for SizeFilter."""

    def test_size_limit(self, tmp_path: Path) -> None:
        """Test file size filtering."""
        filter = SizeFilter(max_size_bytes=100)

        # Create files of different sizes
        small_file = tmp_path / "small.txt"
        small_file.write_text("a" * 50)

        large_file = tmp_path / "large.txt"
        large_file.write_text("a" * 150)

        assert filter.should_include(small_file)
        assert not filter.should_include(large_file)


class TestLanguageFilter:
    """Tests for LanguageFilter."""

    def test_language_filter(self) -> None:
        """Test filtering by supported languages."""
        filter = LanguageFilter({".py", ".java", ".js"})

        assert filter.should_include(Path("test.py"))
        assert filter.should_include(Path("test.java"))
        assert not filter.should_include(Path("test.go"))


class TestFilterChain:
    """Tests for FilterChain builder."""

    def test_chain_building(self) -> None:
        """Test building filter chain."""
        chain = FilterChain()
        composite = (
            chain.with_ignore_patterns(["*.pyc"])
            .with_hidden_files(exclude=True)
            .with_languages({".py", ".java"})
            .build()
        )

        assert isinstance(composite, CompositeFilter)
        assert len(composite.filters) == 3


class TestChangeDetector:
    """Tests for ChangeDetector."""

    def test_detect_new_files(self, tmp_path: Path) -> None:
        """Test detecting new files."""
        detector = ChangeDetector()

        # Create current index (empty)
        index = RepositoryIndex(repo_root=tmp_path, files={})

        # Create new scan
        file1 = tmp_path / "test1.py"
        file1.write_text("test")
        metadata = FileMetadata.from_path(file1, tmp_path, {".py": "python"})

        scan_result = ScanResult(
            files=[metadata],
            total_files=1,
            total_size=metadata.size,
            scan_time=0.1,
            errors=[],
        )

        changes = detector.detect_changes(index, scan_result)

        assert len(changes.new_files) == 1
        assert len(changes.modified_files) == 0
        assert len(changes.deleted_files) == 0

    def test_detect_modified_files(self, tmp_path: Path) -> None:
        """Test detecting modified files."""
        import time

        detector = ChangeDetector()

        # Create file
        file1 = tmp_path / "test.py"
        file1.write_text("old content")

        # Create metadata for current index
        old_metadata = FileMetadata.from_path(file1, tmp_path, {".py": "python"})

        # Wait and modify file
        time.sleep(0.1)
        file1.write_text("new content that is longer")

        # Create metadata for new scan
        new_metadata = FileMetadata.from_path(file1, tmp_path, {".py": "python"})

        # Create index and scan
        index = RepositoryIndex(
            repo_root=tmp_path,
            files={old_metadata.relative_path: old_metadata},
        )

        scan_result = ScanResult(
            files=[new_metadata],
            total_files=1,
            total_size=new_metadata.size,
            scan_time=0.1,
            errors=[],
        )

        changes = detector.detect_changes(index, scan_result)

        assert len(changes.new_files) == 0
        assert len(changes.modified_files) == 1
        assert len(changes.deleted_files) == 0

    def test_detect_deleted_files(self, tmp_path: Path) -> None:
        """Test detecting deleted files."""
        detector = ChangeDetector()

        # Create metadata for file that was in index
        old_path = tmp_path / "deleted.py"
        old_metadata = FileMetadata(
            absolute_path=old_path,
            relative_path=Path("deleted.py"),
            extension=".py",
            size=100,
            mtime=datetime.now(),
            language="python",
        )

        index = RepositoryIndex(
            repo_root=tmp_path,
            files={old_metadata.relative_path: old_metadata},
        )

        # Scan with no files
        scan_result = ScanResult(
            files=[],
            total_files=0,
            total_size=0,
            scan_time=0.1,
            errors=[],
        )

        changes = detector.detect_changes(index, scan_result)

        assert len(changes.new_files) == 0
        assert len(changes.modified_files) == 0
        assert len(changes.deleted_files) == 1


class TestRepositoryScanner:
    """Tests for RepositoryScanner."""

    def test_initialization(self, tmp_path: Path) -> None:
        """Test scanner initialization."""
        scanner = RepositoryScanner(tmp_path)

        assert scanner.repo_root == tmp_path
        assert scanner.max_file_size_mb == 10

    def test_initialization_invalid_path(self) -> None:
        """Test initialization with invalid path."""
        with pytest.raises(ScannerError):
            RepositoryScanner(Path("/nonexistent/path"))

    def test_scan_empty_repository(self, tmp_path: Path) -> None:
        """Test scanning an empty repository."""
        scanner = RepositoryScanner(tmp_path)
        result = scanner.scan()

        assert result.total_files == 0
        assert result.total_size == 0

    def test_scan_repository(self, tmp_path: Path) -> None:
        """Test scanning a repository with files."""
        # Create test files
        py_dir = tmp_path / "src"
        py_dir.mkdir()
        (py_dir / "test1.py").write_text("print('test1')")
        (py_dir / "test2.py").write_text("print('test2')")

        js_dir = tmp_path / "app"
        js_dir.mkdir()
        (js_dir / "app.js").write_text("console.log('test')")

        scanner = RepositoryScanner(tmp_path, use_threading=False)
        result = scanner.scan()

        assert result.total_files == 3
        assert any(f.language == "python" for f in result.files)
        assert any(f.language == "javascript" for f in result.files)

    def test_scan_respects_ignore_patterns(self, tmp_path: Path) -> None:
        """Test that scanner respects ignore patterns."""
        py_file = tmp_path / "test.py"
        py_file.write_text("test")

        pyc_file = tmp_path / "test.pyc"
        pyc_file.write_text("compiled")

        scanner = RepositoryScanner(tmp_path, use_threading=False)
        result = scanner.scan()

        # Should only find .py file, not .pyc
        assert result.total_files == 1
        assert result.files[0].extension == ".py"

    def test_scan_respects_hidden_files(self, tmp_path: Path) -> None:
        """Test that scanner excludes hidden files."""
        (tmp_path / "test.py").write_text("test")
        (tmp_path / ".env").write_text("secret")

        scanner = RepositoryScanner(tmp_path, use_threading=False)
        result = scanner.scan()

        assert result.total_files == 1
        assert result.files[0].absolute_path.name == "test.py"

    def test_scan_directory(self, tmp_path: Path) -> None:
        """Test scanning specific directory."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "test.py").write_text("test")

        scanner = RepositoryScanner(tmp_path)
        result = scanner.scan_directory(Path("src"))

        assert result.total_files == 1

    def test_get_files_by_language(self, tmp_path: Path) -> None:
        """Test filtering files by language."""
        (tmp_path / "test.py").write_text("python")
        (tmp_path / "test.js").write_text("javascript")

        scanner = RepositoryScanner(tmp_path, use_threading=False)
        result = scanner.scan()

        python_files = scanner.get_files_by_language(result, "python")
        assert len(python_files) == 1

    def test_get_statistics(self, tmp_path: Path) -> None:
        """Test getting scan statistics."""
        (tmp_path / "test.py").write_text("python")
        (tmp_path / "test.js").write_text("javascript")

        scanner = RepositoryScanner(tmp_path, use_threading=False)
        result = scanner.scan()

        stats = scanner.get_statistics(result)

        assert stats["total_files"] == 2
        assert "language_distribution" in stats
        assert stats["language_distribution"]["python"] == 1


@pytest.mark.integration
class TestRepositoryScannerIntegration:
    """Integration tests for repository scanner."""

    def test_full_scan_workflow(self, tmp_path: Path) -> None:
        """Test complete scanning workflow."""
        # Create sample repository structure
        src = tmp_path / "src"
        src.mkdir()
        (src / "main.py").write_text("def main(): pass")
        (src / "utils.py").write_text("def util(): pass")

        tests = tmp_path / "tests"
        tests.mkdir()
        (tests / "test_main.py").write_text("def test(): pass")

        # Scan
        scanner = RepositoryScanner(tmp_path, use_threading=False)
        result = scanner.scan()

        # Verify
        assert result.total_files == 3
        assert all(f.language == "python" for f in result.files)
        assert result.total_size > 0
        assert result.scan_time > 0
