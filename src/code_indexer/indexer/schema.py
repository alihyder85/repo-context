"""SQLite DDL and migration management for the code indexer."""
from __future__ import annotations

import sqlite3

from loguru import logger

CURRENT_VERSION = 1

_MIGRATION_1 = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS repositories (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    root_path   TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS files (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_id       INTEGER NOT NULL REFERENCES repositories(id),
    relative_path TEXT NOT NULL,
    absolute_path TEXT NOT NULL,
    language      TEXT NOT NULL,
    size          INTEGER NOT NULL DEFAULT 0,
    mtime         TEXT NOT NULL DEFAULT '',
    hash          TEXT,
    UNIQUE(repo_id, relative_path)
);

CREATE TABLE IF NOT EXISTS symbols (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id        INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    name           TEXT NOT NULL,
    qualified_name TEXT,
    symbol_type    TEXT NOT NULL,
    line_start     INTEGER,
    line_end       INTEGER,
    signature      TEXT,
    docstring      TEXT
);

CREATE TABLE IF NOT EXISTS symbol_refs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    caller_id   INTEGER REFERENCES symbols(id) ON DELETE CASCADE,
    callee_id   INTEGER REFERENCES symbols(id) ON DELETE SET NULL,
    callee_name TEXT NOT NULL,
    ref_type    TEXT NOT NULL,
    line        INTEGER
);

CREATE INDEX IF NOT EXISTS idx_symbols_name    ON symbols(name);
CREATE INDEX IF NOT EXISTS idx_symbols_file_id ON symbols(file_id);
CREATE INDEX IF NOT EXISTS idx_symbols_type    ON symbols(symbol_type);
CREATE INDEX IF NOT EXISTS idx_refs_caller     ON symbol_refs(caller_id);
CREATE INDEX IF NOT EXISTS idx_refs_callee     ON symbol_refs(callee_id);
CREATE INDEX IF NOT EXISTS idx_files_language  ON files(language);
CREATE INDEX IF NOT EXISTS idx_files_repo      ON files(repo_id);

CREATE VIRTUAL TABLE IF NOT EXISTS symbols_fts USING fts5(
    name,
    signature,
    docstring,
    content=symbols,
    content_rowid=id
);
"""

_MIGRATIONS: list[tuple[int, str]] = [
    (1, _MIGRATION_1),
]


def create_tables(conn: sqlite3.Connection) -> None:
    """Create all tables idempotently.

    Safe to call on an existing database — uses IF NOT EXISTS throughout.

    Args:
        conn: Active SQLite connection with foreign_keys and WAL already set.
    """
    conn.executescript(_MIGRATION_1)
    version = _get_version(conn)
    if version == 0:
        conn.execute("INSERT OR IGNORE INTO schema_version(version) VALUES(?)", (CURRENT_VERSION,))
        conn.commit()
    logger.debug("create_tables: schema ready (version={})", CURRENT_VERSION)


def migrate(conn: sqlite3.Connection) -> None:
    """Apply any missing migrations in order.

    Reads the current version from ``schema_version`` and runs each
    migration whose version number is higher.

    Args:
        conn: Active SQLite connection.
    """
    current = _get_version(conn)
    for version, sql in _MIGRATIONS:
        if version > current:
            logger.info("migrate: applying migration {}", version)
            conn.executescript(sql)
            conn.execute(
                "INSERT OR REPLACE INTO schema_version(version) VALUES(?)", (version,)
            )
            conn.commit()
            logger.info("migrate: schema now at version {}", version)


def _get_version(conn: sqlite3.Connection) -> int:
    """Return the current schema version, or 0 if not set."""
    try:
        row = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
        return row[0] or 0
    except sqlite3.OperationalError:
        return 0
