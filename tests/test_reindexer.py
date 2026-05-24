"""Tests for Phase 8: IncrementalReindexer."""
from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from code_indexer.extractor.models import ExtractionResult, ExtractedSymbol, Reference
from code_indexer.indexer.reindexer import IncrementalReindexer, ReindexStats
from code_indexer.indexer.writer import IndexWriter
from code_indexer.parsers.models import ParsedFile
from code_indexer.scanner.models import FileMetadata, ScanResult


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _write_py(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _make_reindexer(repo_root: Path, db_path: Path) -> IncrementalReindexer:
    """Return a reindexer wired to real scanner/parser/extractor."""
    return IncrementalReindexer(repo_root=repo_root, db_path=db_path)


# ------------------------------------------------------------------
# Full index tests
# ------------------------------------------------------------------

def test_full_index_empty_repo():
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        repo.mkdir()
        db = Path(tmp) / "index.db"
        r = _make_reindexer(repo, db)
        stats = r.full_index()
        assert stats.is_full_index is True
        assert stats.files_added == 0
        assert stats.parse_errors == 0


def test_full_index_python_file():
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        _write_py(repo / "mod.py", "def hello():\n    pass\n")
        db = Path(tmp) / "index.db"
        r = _make_reindexer(repo, db)
        stats = r.full_index()
        assert stats.is_full_index is True
        assert stats.files_added >= 1
        assert stats.symbols_written >= 1


def test_run_first_time_is_full_index():
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        _write_py(repo / "a.py", "x = 1\n")
        db = Path(tmp) / "index.db"
        r = _make_reindexer(repo, db)
        stats = r.run()
        assert stats.is_full_index is True


# ------------------------------------------------------------------
# Incremental tests
# ------------------------------------------------------------------

def test_incremental_no_changes():
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        _write_py(repo / "a.py", "x = 1\n")
        db = Path(tmp) / "index.db"
        r = _make_reindexer(repo, db)
        r.run()  # first run — full index
        stats = r.run()  # second run — incremental
        assert stats.is_full_index is False
        assert stats.files_added == 0
        assert stats.files_updated == 0
        assert stats.files_removed == 0


def test_incremental_new_file():
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        _write_py(repo / "a.py", "x = 1\n")
        db = Path(tmp) / "index.db"
        r = _make_reindexer(repo, db)
        r.run()  # full index

        _write_py(repo / "b.py", "y = 2\n")
        r2 = _make_reindexer(repo, db)
        stats = r2.run()
        assert stats.is_full_index is False
        assert stats.files_added == 1


def test_incremental_deleted_file():
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        a_py = repo / "a.py"
        _write_py(a_py, "x = 1\n")
        _write_py(repo / "b.py", "y = 2\n")
        db = Path(tmp) / "index.db"
        r = _make_reindexer(repo, db)
        r.run()

        a_py.unlink()
        r2 = _make_reindexer(repo, db)
        stats = r2.run()
        assert stats.is_full_index is False
        assert stats.files_removed == 1


def test_incremental_modified_file():
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        a_py = repo / "a.py"
        _write_py(a_py, "x = 1\n")
        db = Path(tmp) / "index.db"
        r = _make_reindexer(repo, db)
        r.run()

        import time as _time
        _time.sleep(0.05)  # ensure mtime changes
        a_py.write_text("x = 999\ndef new_fn(): pass\n")

        r2 = _make_reindexer(repo, db)
        stats = r2.run()
        assert stats.is_full_index is False
        assert stats.files_updated == 1


# ------------------------------------------------------------------
# Error handling
# ------------------------------------------------------------------

def test_parse_error_does_not_abort():
    """A single failing file must not stop the whole pipeline."""
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        repo.mkdir()
        db = Path(tmp) / "index.db"

        # Mock a scanner that returns one file, and a parser that always errors
        from code_indexer.scanner.models import ScanResult
        from datetime import datetime

        bad_meta = MagicMock()
        bad_meta.relative_path = Path("bad.py")
        bad_meta.absolute_path = repo / "bad.py"
        bad_meta.language = "python"
        bad_meta.size = 0
        bad_meta.mtime = datetime.now()

        mock_scanner = MagicMock()
        mock_scanner.scan.return_value = ScanResult(
            files=[bad_meta], total_files=1, total_size=0, scan_time=0.0, errors=[]
        )

        mock_parser = MagicMock()
        mock_parser.parse.side_effect = RuntimeError("boom")

        r = IncrementalReindexer(
            repo_root=repo,
            db_path=db,
            scanner=mock_scanner,
            parser_registry=mock_parser,
        )
        stats = r.full_index()
        assert stats.parse_errors == 1
        assert stats.files_added == 0


# ------------------------------------------------------------------
# Cache invalidation
# ------------------------------------------------------------------

def test_cache_invalidated_when_changes_exist():
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        _write_py(repo / "a.py", "x = 1\n")
        db = Path(tmp) / "index.db"

        mock_engine = MagicMock()
        r = IncrementalReindexer(
            repo_root=repo, db_path=db, retrieval_engine=mock_engine
        )
        r.run()  # full index (engine not used for invalidation here)

        _write_py(repo / "b.py", "y = 2\n")
        r2 = IncrementalReindexer(
            repo_root=repo, db_path=db, retrieval_engine=mock_engine
        )
        r2.run()
        mock_engine.invalidate_cache.assert_called_once()
