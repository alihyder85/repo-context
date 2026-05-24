"""Tests for MCP server tool implementations."""
from __future__ import annotations

import os
import sqlite3
import tempfile
from pathlib import Path

import pytest

from code_indexer.indexer.schema import create_tables
from code_indexer.mcp import tools as mcp_tools


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    """Create a minimal seeded SQLite database and return its path."""
    path = tmp_path / "test_index.db"
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    create_tables(conn)

    conn.execute(
        "INSERT INTO repositories (root_path, name, created_at, updated_at) VALUES (?, ?, ?, ?)",
        ("/repo", "test_repo", "2024-01-01T00:00:00", "2024-01-01T00:00:00"),
    )
    repo_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    conn.execute(
        """INSERT INTO files
           (repo_id, relative_path, absolute_path, language, size, mtime)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (repo_id, "payments/processor.py", "/repo/payments/processor.py", "python", 500, "2024-01-01T00:00:00"),
    )
    file_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    conn.execute(
        """INSERT INTO symbols
           (file_id, name, qualified_name, symbol_type, line_start, line_end, signature, docstring)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (file_id, "charge_card", "payments.processor.charge_card",
         "function", 3, 15, "charge_card(amount, card_token)", "Charge a credit card via Stripe."),
    )
    sym_a = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    conn.execute(
        """INSERT INTO symbols
           (file_id, name, qualified_name, symbol_type, line_start, line_end, signature, docstring)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (file_id, "refund", "payments.processor.refund",
         "function", 18, 28, "refund(transaction_id)", None),
    )
    sym_b = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    conn.execute(
        "INSERT INTO symbol_refs (caller_id, callee_id, callee_name, ref_type) VALUES (?, ?, ?, ?)",
        (sym_a, sym_b, "payments.processor.refund", "call"),
    )

    conn.execute("INSERT INTO symbols_fts(symbols_fts) VALUES('rebuild')")
    conn.commit()
    conn.close()
    return path


@pytest.fixture(autouse=True)
def set_db_env(db_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Point all tool calls at the temp database."""
    monkeypatch.setenv("CODE_INDEXER_DB", str(db_path))


# ------------------------------------------------------------------
# get_context
# ------------------------------------------------------------------

class TestGetContext:
    def test_returns_markdown_with_header(self) -> None:
        result = mcp_tools.get_context("charge_card")
        assert "## Context for:" in result
        assert "charge_card" in result

    def test_returns_no_results_message_on_miss(self) -> None:
        result = mcp_tools.get_context("nonexistent_xyz_abc")
        assert "No context found" in result

    def test_respects_token_budget_param(self) -> None:
        result = mcp_tools.get_context("charge_card", token_budget=100)
        assert "Budget: 100" in result


# ------------------------------------------------------------------
# search_symbols
# ------------------------------------------------------------------

class TestSearchSymbols:
    def test_finds_matching_symbol(self) -> None:
        result = mcp_tools.search_symbols("charge_card")
        assert "charge_card" in result

    def test_returns_no_results_message_on_miss(self) -> None:
        result = mcp_tools.search_symbols("totally_unknown_xyz")
        assert "No symbols found" in result

    def test_result_contains_file_path(self) -> None:
        result = mcp_tools.search_symbols("charge_card")
        assert "payments/processor.py" in result


# ------------------------------------------------------------------
# find_symbol
# ------------------------------------------------------------------

class TestFindSymbol:
    def test_exact_match(self) -> None:
        result = mcp_tools.find_symbol("charge_card")
        assert "charge_card" in result
        assert "payments/processor.py" in result

    def test_no_match(self) -> None:
        result = mcp_tools.find_symbol("does_not_exist_abc")
        assert "Symbol not found" in result

    def test_with_symbol_type_filter(self) -> None:
        result = mcp_tools.find_symbol("charge_card", symbol_type="function")
        assert "charge_card" in result

    def test_wrong_symbol_type_returns_not_found(self) -> None:
        result = mcp_tools.find_symbol("charge_card", symbol_type="class")
        assert "Symbol not found" in result


# ------------------------------------------------------------------
# read_snippet
# ------------------------------------------------------------------

class TestReadSnippet:
    def test_reads_real_file(self, tmp_path: Path) -> None:
        src = tmp_path / "sample.py"
        src.write_text("line1\nline2\nline3\nline4\n")
        result = mcp_tools.read_snippet(str(src), 2, 3)
        assert "line2" in result
        assert "line3" in result
        assert "line1" not in result

    def test_missing_file_returns_error_message(self) -> None:
        result = mcp_tools.read_snippet("/nonexistent/path/file.py", 1, 10)
        assert "Could not read" in result


# ------------------------------------------------------------------
# get_dependencies
# ------------------------------------------------------------------

class TestGetDependencies:
    def test_returns_dependencies(self, db_path: Path) -> None:
        conn = sqlite3.connect(str(db_path))
        sym_id = conn.execute(
            "SELECT id FROM symbols WHERE name='charge_card'"
        ).fetchone()[0]
        conn.close()

        result = mcp_tools.get_dependencies(sym_id, max_depth=1)
        assert "refund" in result

    def test_no_deps_returns_message(self, db_path: Path) -> None:
        conn = sqlite3.connect(str(db_path))
        sym_id = conn.execute(
            "SELECT id FROM symbols WHERE name='refund'"
        ).fetchone()[0]
        conn.close()

        result = mcp_tools.get_dependencies(sym_id, max_depth=1)
        assert "No dependencies" in result


# ------------------------------------------------------------------
# DB not found
# ------------------------------------------------------------------

class TestDbNotFound:
    def test_raises_when_db_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CODE_INDEXER_DB", "/tmp/does_not_exist_xyz.db")
        with pytest.raises(FileNotFoundError, match="Database not found"):
            mcp_tools.get_context("anything")
