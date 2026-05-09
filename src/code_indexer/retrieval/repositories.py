"""Raw SQL repository classes for retrieval data access.

No ranking, scoring, or business logic here — only query execution.
Each class receives a sqlite3.Connection so callers control transactions
and connection lifecycle.
"""

from __future__ import annotations

import sqlite3
from typing import Optional

from loguru import logger

from code_indexer.retrieval.models import FileResult, SymbolResult


def _row_to_symbol(row: sqlite3.Row) -> SymbolResult:
    """Convert a DB row to a SymbolResult."""
    return SymbolResult(
        id=row["id"],
        name=row["name"],
        qualified_name=row["qualified_name"],
        symbol_type=row["symbol_type"],
        file_path=row["relative_path"],
        language=row["language"],
        line_start=row["line_start"],
        line_end=row["line_end"],
        signature=row["signature"],
        docstring=row["docstring"],
    )


def _row_to_file(row: sqlite3.Row) -> FileResult:
    """Convert a DB row to a FileResult."""
    return FileResult(
        id=row["id"],
        relative_path=row["relative_path"],
        absolute_path=row["absolute_path"],
        language=row["language"],
        size=row["size"],
        mtime=row["mtime"],
    )


class SymbolRepository:
    """Raw SQL queries for the symbols table."""

    # Common SELECT used across all symbol queries
    _SELECT = """
        SELECT s.id, s.name, s.qualified_name, s.symbol_type,
               s.line_start, s.line_end, s.signature, s.docstring,
               f.relative_path, f.language
        FROM symbols s
        JOIN files f ON f.id = s.file_id
    """

    def find_by_name(
        self,
        conn: sqlite3.Connection,
        name: str,
        symbol_types: Optional[list[str]] = None,
        language: Optional[str] = None,
    ) -> list[SymbolResult]:
        """Find symbols by exact, prefix, or substring name match.

        Results are ordered: exact > prefix > substring.

        Args:
            conn: Active SQLite connection
            name: Symbol name to search
            symbol_types: Optional filter by symbol type(s)
            language: Optional filter by language

        Returns:
            List of matching SymbolResult ordered by match quality
        """
        conditions = ["(s.name = ? OR s.name LIKE ? OR s.name LIKE ?)"]
        params: list = [name, f"{name}%", f"%{name}%"]

        if symbol_types:
            placeholders = ",".join("?" * len(symbol_types))
            conditions.append(f"s.symbol_type IN ({placeholders})")
            params.extend(symbol_types)

        if language:
            conditions.append("f.language = ?")
            params.append(language)

        where = " AND ".join(conditions)
        sql = f"{self._SELECT} WHERE {where} ORDER BY s.name = ? DESC, s.name LIKE ? DESC LIMIT 50"
        params.extend([name, f"{name}%"])

        logger.debug(f"find_by_name: name={name!r}")
        conn.row_factory = sqlite3.Row
        return [_row_to_symbol(r) for r in conn.execute(sql, params).fetchall()]

    def find_by_id(
        self, conn: sqlite3.Connection, symbol_id: int
    ) -> Optional[SymbolResult]:
        """Fetch a single symbol by primary key.

        Args:
            conn: Active SQLite connection
            symbol_id: Symbol primary key

        Returns:
            SymbolResult or None if not found
        """
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            f"{self._SELECT} WHERE s.id = ?", (symbol_id,)
        ).fetchone()
        return _row_to_symbol(row) if row else None

    def search_fts(
        self,
        conn: sqlite3.Connection,
        query: str,
        limit: int = 20,
    ) -> list[SymbolResult]:
        """Full-text search using the symbols_fts FTS5 table.

        Args:
            conn: Active SQLite connection
            query: FTS5 query string
            limit: Maximum results to return

        Returns:
            List of matching SymbolResult (unscored — caller applies ranking)
        """
        sql = f"""
            {self._SELECT}
            JOIN symbols_fts fts ON fts.rowid = s.id
            WHERE symbols_fts MATCH ?
            ORDER BY rank
            LIMIT ?
        """
        logger.debug(f"search_fts: query={query!r}")
        conn.row_factory = sqlite3.Row
        try:
            return [_row_to_symbol(r) for r in conn.execute(sql, (query, limit)).fetchall()]
        except sqlite3.OperationalError as e:
            # FTS table may not exist yet (index not built)
            logger.warning(f"FTS search failed: {e}")
            return []

    def find_callees(
        self, conn: sqlite3.Connection, symbol_id: int
    ) -> list[SymbolResult]:
        """Find symbols called / referenced by the given symbol.

        Args:
            conn: Active SQLite connection
            symbol_id: Caller symbol ID

        Returns:
            List of callee SymbolResult
        """
        sql = f"""
            {self._SELECT}
            JOIN symbol_refs r ON r.callee_id = s.id
            WHERE r.caller_id = ?
        """
        conn.row_factory = sqlite3.Row
        return [_row_to_symbol(r) for r in conn.execute(sql, (symbol_id,)).fetchall()]

    def find_callers(
        self, conn: sqlite3.Connection, symbol_id: int
    ) -> list[SymbolResult]:
        """Find symbols that call / reference the given symbol.

        Args:
            conn: Active SQLite connection
            symbol_id: Callee symbol ID

        Returns:
            List of caller SymbolResult
        """
        sql = f"""
            {self._SELECT}
            JOIN symbol_refs r ON r.caller_id = s.id
            WHERE r.callee_id = ?
        """
        conn.row_factory = sqlite3.Row
        return [_row_to_symbol(r) for r in conn.execute(sql, (symbol_id,)).fetchall()]

    def find_by_file(
        self, conn: sqlite3.Connection, file_id: int
    ) -> list[SymbolResult]:
        """Return all symbols defined in a file.

        Args:
            conn: Active SQLite connection
            file_id: File primary key

        Returns:
            List of SymbolResult ordered by line_start
        """
        sql = f"{self._SELECT} WHERE s.file_id = ? ORDER BY s.line_start"
        conn.row_factory = sqlite3.Row
        return [_row_to_symbol(r) for r in conn.execute(sql, (file_id,)).fetchall()]


class FileRepository:
    """Raw SQL queries for the files table."""

    _SELECT = """
        SELECT id, relative_path, absolute_path, language, size, mtime
        FROM files
    """

    def find_by_path(
        self, conn: sqlite3.Connection, relative_path: str
    ) -> Optional[FileResult]:
        """Find a file by its relative path.

        Args:
            conn: Active SQLite connection
            relative_path: Path relative to repository root

        Returns:
            FileResult or None
        """
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            f"{self._SELECT} WHERE relative_path = ?", (relative_path,)
        ).fetchone()
        return _row_to_file(row) if row else None

    def find_by_language(
        self, conn: sqlite3.Connection, language: str
    ) -> list[FileResult]:
        """Return all files for a given language.

        Args:
            conn: Active SQLite connection
            language: Language name (e.g. 'python')

        Returns:
            List of FileResult
        """
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            f"{self._SELECT} WHERE language = ? ORDER BY relative_path", (language,)
        ).fetchall()
        return [_row_to_file(r) for r in rows]

    def find_by_id(
        self, conn: sqlite3.Connection, file_id: int
    ) -> Optional[FileResult]:
        """Fetch a file by primary key.

        Args:
            conn: Active SQLite connection
            file_id: File primary key

        Returns:
            FileResult or None
        """
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            f"{self._SELECT} WHERE id = ?", (file_id,)
        ).fetchone()
        return _row_to_file(row) if row else None


class ReferenceRepository:
    """Raw SQL queries for the symbol_refs table."""

    def find_imports_for_file(
        self, conn: sqlite3.Connection, file_id: int
    ) -> list[SymbolResult]:
        """Return all symbols imported by a file (import-type references).

        Args:
            conn: Active SQLite connection
            file_id: File whose imports to fetch

        Returns:
            List of imported SymbolResult
        """
        sql = """
            SELECT s.id, s.name, s.qualified_name, s.symbol_type,
                   s.line_start, s.line_end, s.signature, s.docstring,
                   f.relative_path, f.language
            FROM symbols s
            JOIN files f ON f.id = s.file_id
            JOIN symbol_refs r ON r.callee_id = s.id
            JOIN symbols caller_sym ON caller_sym.id = r.caller_id
            WHERE caller_sym.file_id = ? AND r.ref_type = 'import'
        """
        conn.row_factory = sqlite3.Row
        return [_row_to_symbol(r) for r in conn.execute(sql, (file_id,)).fetchall()]

    def find_importers_of_file(
        self, conn: sqlite3.Connection, file_id: int
    ) -> list[FileResult]:
        """Return files that import symbols from the given file.

        Args:
            conn: Active SQLite connection
            file_id: File being imported

        Returns:
            List of importer FileResult
        """
        sql = """
            SELECT DISTINCT f.id, f.relative_path, f.absolute_path,
                            f.language, f.size, f.mtime
            FROM files f
            JOIN symbols caller_sym ON caller_sym.file_id = f.id
            JOIN symbol_refs r ON r.caller_id = caller_sym.id
            JOIN symbols callee_sym ON callee_sym.id = r.callee_id
            WHERE callee_sym.file_id = ? AND r.ref_type = 'import'
        """
        conn.row_factory = sqlite3.Row
        return [_row_to_file(r) for r in conn.execute(sql, (file_id,)).fetchall()]
