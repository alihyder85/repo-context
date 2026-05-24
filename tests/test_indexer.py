"""Tests for Phase 6+7: SQLite indexer and FTS5."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from code_indexer.extractor.models import ExtractedSymbol, ExtractionResult, Reference
from code_indexer.indexer.schema import create_tables, migrate
from code_indexer.indexer.writer import IndexWriter
from code_indexer.scanner.models import FileMetadata


def _make_file_meta(rel: str = "src/foo.py", lang: str = "python") -> FileMetadata:
    meta = MagicMock(spec=FileMetadata)
    meta.relative_path = Path(rel)
    meta.absolute_path = Path(f"/repo/{rel}")
    meta.language = lang
    meta.size = 100
    meta.mtime = "2024-01-01T00:00:00"
    meta.hash = None
    return meta


def _make_symbol(name: str, file_path: str = "src/foo.py") -> ExtractedSymbol:
    return ExtractedSymbol(
        file_path=file_path,
        language="python",
        name=name,
        qualified_name=name,
        symbol_type="function",
        line_start=1,
        line_end=5,
        signature=f"def {name}():",
        docstring=f"Docs for {name}",
    )


def _make_ref(caller: str, callee: str, file_path: str = "src/foo.py") -> Reference:
    return Reference(
        file_path=file_path,
        caller_qualified_name=caller,
        callee_name=callee,
        ref_type="call",
        line=3,
    )


# ------------------------------------------------------------------
# Schema tests
# ------------------------------------------------------------------

def test_create_tables_idempotent():
    with IndexWriter(":memory:") as w:
        create_tables(w._db)  # second call — must not raise
        create_tables(w._db)


def test_migrate_advances_version():
    with IndexWriter(":memory:") as w:
        row = w._db.execute("SELECT MAX(version) FROM schema_version").fetchone()
        assert row[0] == 1


# ------------------------------------------------------------------
# Repository tests
# ------------------------------------------------------------------

def test_write_repository_returns_id():
    with IndexWriter(":memory:") as w:
        rid = w.write_repository("/repo", "myrepo")
        assert rid > 0


def test_write_repository_upsert():
    with IndexWriter(":memory:") as w:
        r1 = w.write_repository("/repo", "old_name")
        r2 = w.write_repository("/repo", "new_name")
        assert r1 == r2
        row = w._db.execute("SELECT name FROM repositories WHERE id=?", (r1,)).fetchone()
        assert row["name"] == "new_name"
        count = w._db.execute("SELECT COUNT(*) FROM repositories").fetchone()[0]
        assert count == 1


# ------------------------------------------------------------------
# File tests
# ------------------------------------------------------------------

def test_write_file_returns_id():
    with IndexWriter(":memory:") as w:
        rid = w.write_repository("/repo", "r")
        fid = w.write_file(_make_file_meta(), rid)
        assert fid > 0


def test_write_file_upsert_no_duplicate():
    with IndexWriter(":memory:") as w:
        rid = w.write_repository("/repo", "r")
        meta = _make_file_meta()
        fid1 = w.write_file(meta, rid)
        fid2 = w.write_file(meta, rid)
        assert fid1 == fid2
        count = w._db.execute("SELECT COUNT(*) FROM files").fetchone()[0]
        assert count == 1


# ------------------------------------------------------------------
# Symbol tests
# ------------------------------------------------------------------

def test_write_symbols_returns_ids():
    with IndexWriter(":memory:") as w:
        rid = w.write_repository("/repo", "r")
        fid = w.write_file(_make_file_meta(), rid)
        symbols = [_make_symbol("foo"), _make_symbol("bar")]
        ids = w.write_symbols(symbols, fid)
        assert len(ids) == 2
        assert all(i > 0 for i in ids)


def test_write_symbols_empty():
    with IndexWriter(":memory:") as w:
        rid = w.write_repository("/repo", "r")
        fid = w.write_file(_make_file_meta(), rid)
        assert w.write_symbols([], fid) == []


# ------------------------------------------------------------------
# Reference tests
# ------------------------------------------------------------------

def test_write_references_resolved():
    with IndexWriter(":memory:") as w:
        rid = w.write_repository("/repo", "r")
        fid = w.write_file(_make_file_meta(), rid)
        ids = w.write_symbols([_make_symbol("foo"), _make_symbol("bar")], fid)
        sym_map = {"foo": ids[0], "bar": ids[1]}
        ref = _make_ref("foo", "bar")
        w.write_references([ref], sym_map)
        row = w._db.execute("SELECT callee_id FROM symbol_refs").fetchone()
        assert row["callee_id"] == ids[1]


def test_write_references_unresolved_callee_is_null():
    with IndexWriter(":memory:") as w:
        rid = w.write_repository("/repo", "r")
        fid = w.write_file(_make_file_meta(), rid)
        ids = w.write_symbols([_make_symbol("foo")], fid)
        ref = _make_ref("foo", "external.thing")
        w.write_references([ref], {"foo": ids[0]})
        row = w._db.execute("SELECT callee_id FROM symbol_refs").fetchone()
        assert row["callee_id"] is None


def test_write_references_empty():
    with IndexWriter(":memory:") as w:
        w.write_references([], {})  # must not raise


# ------------------------------------------------------------------
# Delete tests
# ------------------------------------------------------------------

def test_delete_file_cascades():
    with IndexWriter(":memory:") as w:
        rid = w.write_repository("/repo", "r")
        fid = w.write_file(_make_file_meta(), rid)
        ids = w.write_symbols([_make_symbol("foo"), _make_symbol("bar")], fid)
        sym_map = {"foo": ids[0], "bar": ids[1]}
        w.write_references([_make_ref("foo", "bar")], sym_map)

        w.delete_file(fid)

        assert w._db.execute("SELECT COUNT(*) FROM files").fetchone()[0] == 0
        assert w._db.execute("SELECT COUNT(*) FROM symbols").fetchone()[0] == 0
        assert w._db.execute("SELECT COUNT(*) FROM symbol_refs").fetchone()[0] == 0


# ------------------------------------------------------------------
# FTS tests
# ------------------------------------------------------------------

def test_rebuild_fts_no_error():
    with IndexWriter(":memory:") as w:
        rid = w.write_repository("/repo", "r")
        fid = w.write_file(_make_file_meta(), rid)
        w.write_symbols([_make_symbol("my_function")], fid)
        w.rebuild_fts()  # must not raise


# ------------------------------------------------------------------
# Integration test
# ------------------------------------------------------------------

def test_full_extraction_result_round_trip():
    with IndexWriter(":memory:") as w:
        rid = w.write_repository("/repo", "r")
        meta = _make_file_meta("src/mod.py")
        fid = w.write_file(meta, rid)

        symbols = [
            _make_symbol("alpha", "src/mod.py"),
            _make_symbol("beta", "src/mod.py"),
        ]
        ids = w.write_symbols(symbols, fid)
        sym_map = {s.qualified_name: ids[i] for i, s in enumerate(symbols)}
        refs = [_make_ref("alpha", "beta", "src/mod.py")]
        w.write_references(refs, sym_map)
        w.rebuild_fts()

        rows = w._db.execute("SELECT name FROM symbols WHERE file_id=?", (fid,)).fetchall()
        names = {r["name"] for r in rows}
        assert names == {"alpha", "beta"}

        ref_row = w._db.execute("SELECT callee_id FROM symbol_refs").fetchone()
        assert ref_row["callee_id"] == ids[1]


def test_cross_file_callee_resolution():
    with IndexWriter(":memory:") as w:
        rid = w.write_repository("/repo", "r")
        fid_a = w.write_file(_make_file_meta("src/a.py"), rid)
        fid_b = w.write_file(_make_file_meta("src/b.py"), rid)

        ids_a = w.write_symbols([_make_symbol("helper", "src/a.py")], fid_a)
        ids_b = w.write_symbols([_make_symbol("caller_fn", "src/b.py")], fid_b)

        sym_map = {"helper": ids_a[0], "caller_fn": ids_b[0]}
        ref = Reference(
            file_path="src/b.py",
            caller_qualified_name="caller_fn",
            callee_name="helper",
            ref_type="call",
            line=10,
        )
        w.write_references([ref], sym_map)

        row = w._db.execute("SELECT callee_id FROM symbol_refs").fetchone()
        assert row["callee_id"] == ids_a[0]


def test_file_with_zero_symbols():
    with IndexWriter(":memory:") as w:
        rid = w.write_repository("/repo", "r")
        fid = w.write_file(_make_file_meta(), rid)
        ids = w.write_symbols([], fid)
        assert ids == []
        count = w._db.execute("SELECT COUNT(*) FROM symbols").fetchone()[0]
        assert count == 0
