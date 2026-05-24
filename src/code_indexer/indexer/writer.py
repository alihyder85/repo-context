"""IndexWriter — all write operations against the SQLite index."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from loguru import logger

from code_indexer.extractor.models import ExtractedSymbol, Reference
from code_indexer.indexer.schema import create_tables, migrate
from code_indexer.scanner.models import FileMetadata
from code_indexer.utils.exceptions import DatabaseError


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class IndexWriter:
    """Owns a single SQLite connection and exposes the full write API.

    Use as a context manager to ensure the connection is closed::

        with IndexWriter(db_path=Path("index.db")) as writer:
            repo_id = writer.write_repository("/repo", "myrepo")
            ...

    Args:
        db_path: Path to the SQLite database file.  Use ``:memory:`` for tests.
    """

    def __init__(self, db_path: Path | str) -> None:
        self._db_path = str(db_path)
        self._conn: Optional[sqlite3.Connection] = None

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def open(self) -> None:
        """Open the connection and prepare the schema."""
        try:
            conn = sqlite3.connect(self._db_path)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.row_factory = sqlite3.Row
            self._conn = conn
        except sqlite3.Error as exc:
            raise DatabaseError(f"Cannot open database {self._db_path}: {exc}") from exc
        migrate(self._conn)
        create_tables(self._conn)

    def close(self) -> None:
        """Close the connection if open."""
        if self._conn:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> "IndexWriter":
        self.open()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    @property
    def _db(self) -> sqlite3.Connection:
        if self._conn is None:
            raise DatabaseError("IndexWriter is not open — call open() or use as context manager")
        return self._conn

    # ------------------------------------------------------------------
    # Write API
    # ------------------------------------------------------------------

    def write_repository(self, repo_root: str, name: str) -> int:
        """Upsert a repository row and return its primary key.

        Args:
            repo_root: Absolute path to the repository root.
            name: Human-readable repository name.

        Returns:
            Repository primary key.

        Raises:
            DatabaseError: On write failure.
        """
        now = _now()
        try:
            with self._db:
                self._db.execute(
                    """
                    INSERT INTO repositories(root_path, name, created_at, updated_at)
                    VALUES(?, ?, ?, ?)
                    ON CONFLICT(root_path) DO UPDATE SET name=excluded.name, updated_at=excluded.updated_at
                    """,
                    (repo_root, name, now, now),
                )
            row = self._db.execute(
                "SELECT id FROM repositories WHERE root_path=?", (repo_root,)
            ).fetchone()
            repo_id: int = row["id"]
            logger.debug("write_repository: repo_id={}", repo_id)
            return repo_id
        except sqlite3.Error as exc:
            raise DatabaseError(f"write_repository failed: {exc}") from exc

    def write_file(self, file_meta: FileMetadata, repo_id: int) -> int:
        """Upsert a file row and return its primary key.

        Args:
            file_meta: Scanner metadata for the file.
            repo_id: Parent repository primary key.

        Returns:
            File primary key.

        Raises:
            DatabaseError: On write failure.
        """
        mtime = str(file_meta.mtime)
        size = file_meta.size
        rel = str(file_meta.relative_path)
        abs_ = str(file_meta.absolute_path)
        lang = file_meta.language
        hash_ = getattr(file_meta, "hash", None)
        try:
            with self._db:
                self._db.execute(
                    """
                    INSERT INTO files(repo_id, relative_path, absolute_path, language, size, mtime, hash)
                    VALUES(?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(repo_id, relative_path) DO UPDATE SET
                        absolute_path=excluded.absolute_path,
                        language=excluded.language,
                        size=excluded.size,
                        mtime=excluded.mtime,
                        hash=excluded.hash
                    """,
                    (repo_id, rel, abs_, lang, size, mtime, hash_),
                )
            row = self._db.execute(
                "SELECT id FROM files WHERE repo_id=? AND relative_path=?", (repo_id, rel)
            ).fetchone()
            file_id: int = row["id"]
            logger.debug("write_file: file_id={} path={}", file_id, rel)
            return file_id
        except sqlite3.Error as exc:
            raise DatabaseError(f"write_file failed for {rel}: {exc}") from exc

    def write_symbols(self, symbols: list[ExtractedSymbol], file_id: int) -> list[int]:
        """Bulk-insert symbols for a file.

        Args:
            symbols: Extracted symbols for the file.
            file_id: Parent file primary key.

        Returns:
            List of inserted symbol primary keys (same order as input).

        Raises:
            DatabaseError: On write failure.
        """
        if not symbols:
            return []
        rows = [
            (
                file_id,
                s.name,
                s.qualified_name,
                s.symbol_type,
                s.line_start,
                s.line_end,
                s.signature,
                s.docstring,
            )
            for s in symbols
        ]
        try:
            with self._db:
                self._db.executemany(
                    """
                    INSERT INTO symbols(file_id, name, qualified_name, symbol_type,
                                        line_start, line_end, signature, docstring)
                    VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    rows,
                )
            id_rows = self._db.execute(
                "SELECT id FROM symbols WHERE file_id=? ORDER BY id", (file_id,)
            ).fetchall()
            ids = [r["id"] for r in id_rows]
            logger.debug("write_symbols: {} symbols for file_id={}", len(ids), file_id)
            return ids
        except sqlite3.Error as exc:
            raise DatabaseError(f"write_symbols failed for file_id={file_id}: {exc}") from exc

    def write_references(
        self, refs: list[Reference], symbol_id_map: dict[str, int]
    ) -> None:
        """Bulk-insert references, resolving callee names to IDs where possible.

        Unresolvable callee names are stored with ``callee_id=NULL``.

        Args:
            refs: Extracted references.
            symbol_id_map: Mapping from qualified_name to symbol primary key
                across all files in the current batch.

        Raises:
            DatabaseError: On write failure.
        """
        if not refs:
            return
        caller_id_map = symbol_id_map  # same map is used for caller lookup
        rows = []
        for r in refs:
            caller_id = caller_id_map.get(r.caller_qualified_name)
            callee_id = symbol_id_map.get(r.callee_name)
            rows.append((caller_id, callee_id, r.callee_name, r.ref_type, r.line))
        try:
            with self._db:
                self._db.executemany(
                    """
                    INSERT INTO symbol_refs(caller_id, callee_id, callee_name, ref_type, line)
                    VALUES(?, ?, ?, ?, ?)
                    """,
                    rows,
                )
            logger.debug("write_references: {} refs", len(rows))
        except sqlite3.Error as exc:
            raise DatabaseError(f"write_references failed: {exc}") from exc

    def delete_file(self, file_id: int) -> None:
        """Delete a file row and cascade to its symbols and references.

        Args:
            file_id: Primary key of the file to remove.

        Raises:
            DatabaseError: On write failure.
        """
        try:
            with self._db:
                self._db.execute("DELETE FROM files WHERE id=?", (file_id,))
            logger.debug("delete_file: file_id={}", file_id)
        except sqlite3.Error as exc:
            raise DatabaseError(f"delete_file failed for file_id={file_id}: {exc}") from exc

    def rebuild_fts(self) -> None:
        """Rebuild the FTS5 content table from the symbols table.

        Raises:
            DatabaseError: On rebuild failure.
        """
        try:
            with self._db:
                self._db.execute("INSERT INTO symbols_fts(symbols_fts) VALUES('rebuild')")
            logger.debug("rebuild_fts: FTS index rebuilt")
        except sqlite3.Error as exc:
            raise DatabaseError(f"rebuild_fts failed: {exc}") from exc

    def get_file_id(self, repo_id: int, relative_path: str) -> int | None:
        """Look up a file's primary key by path.

        Args:
            repo_id: Repository primary key.
            relative_path: Path relative to the repository root.

        Returns:
            File primary key or None if not found.
        """
        row = self._db.execute(
            "SELECT id FROM files WHERE repo_id=? AND relative_path=?",
            (repo_id, relative_path),
        ).fetchone()
        return row["id"] if row else None
