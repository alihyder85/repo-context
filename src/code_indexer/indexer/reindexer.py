"""IncrementalReindexer — orchestrates the full scan → parse → extract → index pipeline."""
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from loguru import logger

from code_indexer.extractor import ExtractorRegistry
from code_indexer.extractor.models import ExtractionResult, Reference
from code_indexer.indexer.writer import IndexWriter
from code_indexer.parsers.registry import ParserRegistry
from code_indexer.retrieval.engine import RetrievalEngine
from code_indexer.scanner import ChangeDetector, RepositoryScanner
from code_indexer.scanner.models import FileMetadata, RepositoryIndex, ScanResult
from code_indexer.utils.config import settings
from code_indexer.utils.exceptions import IndexerError


@dataclass
class ReindexStats:
    """Statistics returned after every reindex run.

    Attributes:
        files_added: Number of new files written.
        files_updated: Number of modified files re-indexed.
        files_removed: Number of deleted files removed.
        files_unchanged: Number of files with no changes.
        symbols_written: Total symbol rows inserted.
        references_written: Total reference rows inserted.
        parse_errors: Number of files that failed to parse or extract.
        duration_seconds: Wall-clock time for the entire run.
        is_full_index: True if this was a full (not incremental) run.
    """

    files_added: int = 0
    files_updated: int = 0
    files_removed: int = 0
    files_unchanged: int = 0
    symbols_written: int = 0
    references_written: int = 0
    parse_errors: int = 0
    duration_seconds: float = 0.0
    is_full_index: bool = False


class IncrementalReindexer:
    """Ties the scanner, parser, extractor, and indexer into one pipeline.

    On first run performs a full index.  On subsequent runs it reads the
    previously indexed file metadata from the DB to detect changes and only
    re-indexes the files that changed.

    All dependencies are injected for testability — defaults use ``settings``.

    Usage::

        reindexer = IncrementalReindexer(
            repo_root=Path("/path/to/repo"),
            db_path=Path("index.db"),
        )
        stats = reindexer.run()
    """

    def __init__(
        self,
        repo_root: Path,
        db_path: Path,
        scanner: Optional[RepositoryScanner] = None,
        parser_registry: Optional[ParserRegistry] = None,
        extractor_registry: Optional[ExtractorRegistry] = None,
        writer: Optional[IndexWriter] = None,
        retrieval_engine: Optional[RetrievalEngine] = None,
    ) -> None:
        self._repo_root = repo_root
        self._db_path = db_path
        self._scanner = scanner or RepositoryScanner(
            repo_root=repo_root,
            ignore_patterns=settings.ignore_patterns,
            max_file_size_mb=settings.max_file_size_mb,
        )
        self._parser_registry = parser_registry or ParserRegistry()
        self._extractor_registry = extractor_registry or ExtractorRegistry()
        self._writer = writer or IndexWriter(db_path)
        self._retrieval_engine = retrieval_engine or RetrievalEngine(db_path)
        self._change_detector = ChangeDetector(use_hash=False)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self) -> ReindexStats:
        """Run a full or incremental reindex depending on DB state.

        Returns:
            ReindexStats describing what changed.

        Raises:
            IndexerError: If the database cannot be opened.
        """
        self._open_writer()
        try:
            repo_id = self._writer.write_repository(
                str(self._repo_root), self._repo_root.name
            )
            existing_index = self._load_index_from_db(repo_id)
            is_full = not existing_index.files
            if is_full:
                return self._full_index_internal(repo_id)
            return self._incremental_index(repo_id, existing_index)
        finally:
            self._writer.close()

    def full_index(self) -> ReindexStats:
        """Force a full reindex regardless of existing state.

        Returns:
            ReindexStats describing the run.

        Raises:
            IndexerError: If the database cannot be opened.
        """
        self._open_writer()
        try:
            repo_id = self._writer.write_repository(
                str(self._repo_root), self._repo_root.name
            )
            return self._full_index_internal(repo_id)
        finally:
            self._writer.close()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _open_writer(self) -> None:
        try:
            self._writer.open()
        except Exception as exc:
            raise IndexerError(f"Cannot open database {self._db_path}: {exc}") from exc

    def _load_index_from_db(self, repo_id: int) -> RepositoryIndex:
        """Build a RepositoryIndex from the files already in the DB."""
        rows = self._writer._db.execute(
            "SELECT relative_path, absolute_path, language, size, mtime FROM files WHERE repo_id=?",
            (repo_id,),
        ).fetchall()
        files: dict[Path, FileMetadata] = {}
        for row in rows:
            rel = Path(row["relative_path"])
            try:
                mtime = datetime.fromisoformat(row["mtime"])
            except ValueError:
                mtime = datetime.min
            meta = FileMetadata(
                absolute_path=Path(row["absolute_path"]),
                relative_path=rel,
                extension=rel.suffix,
                size=row["size"],
                mtime=mtime,
                language=row["language"],
            )
            files[rel] = meta
        return RepositoryIndex(repo_root=self._repo_root, files=files)

    def _full_index_internal(self, repo_id: int) -> ReindexStats:
        t0 = time.monotonic()
        scan = self._scanner.scan()
        logger.info("full_index: {} files to index", len(scan.files))

        stats = ReindexStats(is_full_index=True)
        symbol_id_map: dict[str, int] = {}
        all_refs: list[Reference] = []

        for file_meta in scan.files:
            result = self._process_file(file_meta, repo_id, symbol_id_map, all_refs)
            if result is None:
                stats.parse_errors += 1
            else:
                stats.files_added += 1
                stats.symbols_written += result

        self._flush_references(all_refs, symbol_id_map)
        stats.references_written = len(all_refs)
        self._writer.rebuild_fts()

        stats.duration_seconds = time.monotonic() - t0
        logger.info(
            "full_index done: {} files, {} symbols, {} refs, {:.2f}s",
            stats.files_added, stats.symbols_written,
            stats.references_written, stats.duration_seconds,
        )
        return stats

    def _incremental_index(
        self, repo_id: int, existing_index: RepositoryIndex
    ) -> ReindexStats:
        t0 = time.monotonic()
        scan = self._scanner.scan()
        changed = self._change_detector.detect_changes(existing_index, scan)

        stats = ReindexStats(is_full_index=False)
        symbol_id_map: dict[str, int] = {}
        all_refs: list[Reference] = []

        for file_meta in changed.deleted_files:
            fid = self._writer.get_file_id(repo_id, str(file_meta.relative_path))
            if fid is not None:
                try:
                    self._writer.delete_file(fid)
                except Exception as exc:
                    logger.warning("delete_file failed {}: {}", file_meta.relative_path, exc)
            stats.files_removed += 1

        for file_meta in changed.modified_files:
            fid = self._writer.get_file_id(repo_id, str(file_meta.relative_path))
            if fid is not None:
                try:
                    self._writer.delete_file(fid)
                except Exception as exc:
                    logger.warning("delete modified file {}: {}", file_meta.relative_path, exc)
            result = self._process_file(file_meta, repo_id, symbol_id_map, all_refs)
            if result is None:
                stats.parse_errors += 1
            else:
                stats.files_updated += 1
                stats.symbols_written += result

        for file_meta in changed.new_files:
            result = self._process_file(file_meta, repo_id, symbol_id_map, all_refs)
            if result is None:
                stats.parse_errors += 1
            else:
                stats.files_added += 1
                stats.symbols_written += result

        total_active = len(scan.files)
        stats.files_unchanged = max(
            0,
            total_active - stats.files_added - stats.files_updated,
        )

        if changed.has_changes:
            self._flush_references(all_refs, symbol_id_map)
            stats.references_written = len(all_refs)
            self._writer.rebuild_fts()
            self._retrieval_engine.invalidate_cache()

        stats.duration_seconds = time.monotonic() - t0
        logger.info(
            "incremental done: +{} ~{} -{} unchanged={} syms={} {:.2f}s",
            stats.files_added, stats.files_updated, stats.files_removed,
            stats.files_unchanged, stats.symbols_written, stats.duration_seconds,
        )
        return stats

    def _process_file(
        self,
        file_meta: FileMetadata,
        repo_id: int,
        symbol_id_map: dict[str, int],
        all_refs: list[Reference],
    ) -> Optional[int]:
        """Parse, extract, and write a single file.

        Returns:
            Number of symbols written, or None on error.
        """
        try:
            parsed = self._parser_registry.parse(file_meta)
            extraction = self._extractor_registry.extract(parsed)
            file_id = self._writer.write_file(file_meta, repo_id)
            sym_ids = self._writer.write_symbols(extraction.symbols, file_id)
            for sym, sid in zip(extraction.symbols, sym_ids):
                symbol_id_map[sym.qualified_name] = sid
            all_refs.extend(extraction.references)
            return len(sym_ids)
        except Exception as exc:
            logger.warning("_process_file failed {}: {}", file_meta.relative_path, exc)
            return None

    def _flush_references(
        self, refs: list[Reference], symbol_id_map: dict[str, int]
    ) -> None:
        try:
            self._writer.write_references(refs, symbol_id_map)
        except Exception as exc:
            logger.warning("_flush_references failed: {}", exc)
