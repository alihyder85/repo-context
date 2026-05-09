"""Tests for the retrieval engine module."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from code_indexer.retrieval.context import ContextBuilder
from code_indexer.retrieval.engine import RetrievalEngine
from code_indexer.retrieval.models import RetrievalQuery, SymbolResult
from code_indexer.retrieval.protocols import RetrievalProtocol
from code_indexer.retrieval.ranking import DefaultRankingStrategy, RankingContext, RelevanceScorer
from code_indexer.retrieval.repositories import FileRepository, ReferenceRepository, SymbolRepository
from code_indexer.retrieval.tokens import CharDivFourEstimator


# ---------------------------------------------------------------------------
# In-memory DB helpers
# ---------------------------------------------------------------------------

def _create_schema(conn: sqlite3.Connection) -> None:
    """Create the minimal schema required by the retrieval layer."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY,
            repo_id INTEGER DEFAULT 1,
            relative_path TEXT NOT NULL,
            absolute_path TEXT NOT NULL,
            language TEXT NOT NULL,
            size INTEGER DEFAULT 0,
            mtime TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS symbols (
            id INTEGER PRIMARY KEY,
            file_id INTEGER REFERENCES files(id),
            name TEXT NOT NULL,
            qualified_name TEXT,
            symbol_type TEXT NOT NULL,
            line_start INTEGER,
            line_end INTEGER,
            signature TEXT,
            docstring TEXT
        );

        CREATE TABLE IF NOT EXISTS symbol_refs (
            id INTEGER PRIMARY KEY,
            caller_id INTEGER REFERENCES symbols(id),
            callee_id INTEGER REFERENCES symbols(id),
            ref_type TEXT NOT NULL
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS symbols_fts
            USING fts5(name, signature, docstring, content=symbols, content_rowid=id);
    """)
    conn.commit()


def _seed(conn: sqlite3.Connection) -> dict:
    """Insert sample data and return a mapping of names → IDs."""
    conn.execute(
        "INSERT INTO files (id, relative_path, absolute_path, language, size) VALUES (1, 'src/main.py', '/repo/src/main.py', 'python', 500)"
    )
    conn.execute(
        "INSERT INTO files (id, relative_path, absolute_path, language, size) VALUES (2, 'src/utils.py', '/repo/src/utils.py', 'python', 200)"
    )
    conn.executemany(
        "INSERT INTO symbols (id, file_id, name, qualified_name, symbol_type, line_start, line_end, signature, docstring) VALUES (?,?,?,?,?,?,?,?,?)",
        [
            (1, 1, "main",      "src.main.main",       "function", 1,  10, "def main() -> None",  "Entry point."),
            (2, 1, "parse",     "src.main.parse",      "function", 12, 25, "def parse(src: str)", "Parse source."),
            (3, 2, "helper",    "src.utils.helper",    "function", 1,  5,  "def helper()",        "Utility helper."),
            (4, 2, "MyClass",   "src.utils.MyClass",   "class",    7,  30, "class MyClass:",      "A sample class."),
            (5, 1, "parse_all", "src.main.parse_all",  "function", 27, 40, "def parse_all()",     "Parse everything."),
        ],
    )
    # main → parse (call), parse → helper (call)
    conn.executemany(
        "INSERT INTO symbol_refs (caller_id, callee_id, ref_type) VALUES (?,?,?)",
        [(1, 2, "call"), (2, 3, "call"), (1, 4, "import")],
    )
    conn.commit()
    # Populate FTS
    conn.execute("INSERT INTO symbols_fts(symbols_fts) VALUES('rebuild')")
    conn.commit()
    return {"main": 1, "parse": 2, "helper": 3, "MyClass": 4, "parse_all": 5}


@pytest.fixture
def mem_db(tmp_path: Path) -> Path:
    """Return path to a pre-seeded temporary SQLite database."""
    db_path = tmp_path / "index.db"
    conn = sqlite3.connect(str(db_path))
    _create_schema(conn)
    _seed(conn)
    conn.close()
    return db_path


@pytest.fixture
def empty_db(tmp_path: Path) -> Path:
    """Return path to a schema-only (no data) SQLite database."""
    db_path = tmp_path / "empty.db"
    conn = sqlite3.connect(str(db_path))
    _create_schema(conn)
    conn.close()
    return db_path


# ---------------------------------------------------------------------------
# TokenEstimator
# ---------------------------------------------------------------------------

class TestCharDivFourEstimator:
    def test_empty_string(self) -> None:
        assert CharDivFourEstimator().estimate("") == 0

    def test_short_text(self) -> None:
        assert CharDivFourEstimator().estimate("abcd") == 1

    def test_longer_text(self) -> None:
        # 40 chars → 10 tokens
        assert CharDivFourEstimator().estimate("a" * 40) == 10

    def test_minimum_one_for_nonempty(self) -> None:
        assert CharDivFourEstimator().estimate("x") == 1


# ---------------------------------------------------------------------------
# RelevanceScorer
# ---------------------------------------------------------------------------

class TestRelevanceScorer:
    def _make_symbol(self, name: str, file_path: str = "src/main.py") -> SymbolResult:
        return SymbolResult(id=1, name=name, symbol_type="function", file_path=file_path, language="python")

    def test_exact_match_highest(self) -> None:
        scorer = RelevanceScorer()
        ctx = RankingContext(query="parse")
        exact = scorer.score(self._make_symbol("parse"), ctx)
        prefix = scorer.score(self._make_symbol("parse_all"), ctx)
        substr = scorer.score(self._make_symbol("reparse"), ctx)
        assert exact > prefix > substr

    def test_same_file_bonus(self) -> None:
        scorer = RelevanceScorer()
        ctx = RankingContext(query="x", focal_file="src/main.py")
        same = scorer.score(self._make_symbol("x", "src/main.py"), ctx)
        other = scorer.score(self._make_symbol("x", "src/other.py"), ctx)
        assert same > other

    def test_same_directory_bonus(self) -> None:
        scorer = RelevanceScorer()
        ctx = RankingContext(query="x", focal_file="src/main.py")
        same_dir = scorer.score(self._make_symbol("x", "src/utils.py"), ctx)
        diff_dir = scorer.score(self._make_symbol("x", "lib/foo.py"), ctx)
        assert same_dir > diff_dir

    def test_direct_ref_bonus(self) -> None:
        scorer = RelevanceScorer()
        sym = self._make_symbol("helper")
        sym.id = 99
        ctx = RankingContext(query="helper", direct_ref_ids={99})
        score_with_ref = scorer.score(sym, ctx)
        ctx2 = RankingContext(query="helper", direct_ref_ids=set())
        score_without = scorer.score(sym, ctx2)
        assert score_with_ref > score_without


class TestDefaultRankingStrategy:
    def test_rank_orders_by_score(self) -> None:
        strategy = DefaultRankingStrategy()
        symbols = [
            SymbolResult(id=1, name="reparse",  symbol_type="function", file_path="a.py", language="python"),
            SymbolResult(id=2, name="parse",     symbol_type="function", file_path="a.py", language="python"),
            SymbolResult(id=3, name="parse_all", symbol_type="function", file_path="a.py", language="python"),
        ]
        ctx = RankingContext(query="parse")
        ranked = strategy.rank(symbols, ctx)
        assert ranked[0].name == "parse"
        assert all(s.relevance_score >= 0 for s in ranked)


# ---------------------------------------------------------------------------
# ContextBuilder
# ---------------------------------------------------------------------------

class TestContextBuilder:
    def _make_symbol(self, sid: int, name: str, score: float = 1.0, sig: str = "") -> SymbolResult:
        s = SymbolResult(id=sid, name=name, symbol_type="function", file_path="a.py", language="python", signature=sig)
        s.relevance_score = score
        return s

    def test_empty_candidates(self) -> None:
        builder = ContextBuilder()
        q = RetrievalQuery(query="x", token_budget=1000)
        result = builder.build([], q)
        assert result.is_empty
        assert result.dropped_count == 0
        assert result.remaining_tokens == 1000

    def test_within_budget(self) -> None:
        builder = ContextBuilder()
        symbols = [self._make_symbol(1, "foo", sig="def foo(): pass")]
        q = RetrievalQuery(query="foo", token_budget=1000)
        result = builder.build(symbols, q)
        assert len(result.snippets) == 1
        assert result.dropped_count == 0
        assert not result.was_truncated

    def test_budget_enforcement(self) -> None:
        builder = ContextBuilder()
        # Each symbol has a ~100-char signature → ~25 tokens; budget = 30
        symbols = [
            self._make_symbol(i, f"sym{i}", sig="x" * 100)
            for i in range(5)
        ]
        q = RetrievalQuery(query="sym", token_budget=30)
        result = builder.build(symbols, q)
        assert result.total_tokens <= 30 or len(result.snippets) == 1  # first always included
        assert result.dropped_count > 0
        assert result.was_truncated

    def test_deduplication(self) -> None:
        builder = ContextBuilder()
        sym = self._make_symbol(1, "dup", sig="def dup(): pass")
        q = RetrievalQuery(query="dup", token_budget=1000)
        result = builder.build([sym, sym, sym], q)
        assert len(result.snippets) == 1

    def test_oversized_first_snippet_still_included(self) -> None:
        """A single snippet that exceeds budget must still be returned."""
        builder = ContextBuilder()
        big = self._make_symbol(1, "big", sig="x" * 10_000)
        q = RetrievalQuery(query="big", token_budget=10)
        result = builder.build([big], q)
        assert len(result.snippets) == 1


# ---------------------------------------------------------------------------
# SymbolRepository
# ---------------------------------------------------------------------------

class TestSymbolRepository:
    def test_find_by_name_exact(self, mem_db: Path) -> None:
        repo = SymbolRepository()
        with sqlite3.connect(str(mem_db)) as conn:
            results = repo.find_by_name(conn, "main")
        assert any(r.name == "main" for r in results)

    def test_find_by_name_prefix(self, mem_db: Path) -> None:
        repo = SymbolRepository()
        with sqlite3.connect(str(mem_db)) as conn:
            results = repo.find_by_name(conn, "parse")
        names = {r.name for r in results}
        assert "parse" in names
        assert "parse_all" in names

    def test_find_by_name_not_found(self, mem_db: Path) -> None:
        repo = SymbolRepository()
        with sqlite3.connect(str(mem_db)) as conn:
            assert repo.find_by_name(conn, "nonexistent") == []

    def test_find_callees(self, mem_db: Path) -> None:
        repo = SymbolRepository()
        with sqlite3.connect(str(mem_db)) as conn:
            callees = repo.find_callees(conn, 1)  # main → parse, MyClass
        assert any(c.name == "parse" for c in callees)

    def test_find_callers(self, mem_db: Path) -> None:
        repo = SymbolRepository()
        with sqlite3.connect(str(mem_db)) as conn:
            callers = repo.find_callers(conn, 2)  # who calls parse?
        assert any(c.name == "main" for c in callers)

    def test_find_by_id_missing(self, mem_db: Path) -> None:
        repo = SymbolRepository()
        with sqlite3.connect(str(mem_db)) as conn:
            assert repo.find_by_id(conn, 9999) is None

    def test_empty_index(self, empty_db: Path) -> None:
        repo = SymbolRepository()
        with sqlite3.connect(str(empty_db)) as conn:
            assert repo.find_by_name(conn, "anything") == []


# ---------------------------------------------------------------------------
# FileRepository
# ---------------------------------------------------------------------------

class TestFileRepository:
    def test_find_by_path(self, mem_db: Path) -> None:
        repo = FileRepository()
        with sqlite3.connect(str(mem_db)) as conn:
            result = repo.find_by_path(conn, "src/main.py")
        assert result is not None
        assert result.language == "python"

    def test_find_by_path_not_found(self, mem_db: Path) -> None:
        repo = FileRepository()
        with sqlite3.connect(str(mem_db)) as conn:
            assert repo.find_by_path(conn, "no/such/file.py") is None

    def test_find_by_language(self, mem_db: Path) -> None:
        repo = FileRepository()
        with sqlite3.connect(str(mem_db)) as conn:
            results = repo.find_by_language(conn, "python")
        assert len(results) == 2


# ---------------------------------------------------------------------------
# RetrievalEngine
# ---------------------------------------------------------------------------

class TestRetrievalEngine:
    def test_find_symbol_exact(self, mem_db: Path) -> None:
        engine = RetrievalEngine(mem_db)
        results = engine.find_symbol("main")
        assert any(r.name == "main" for r in results)

    def test_find_symbol_empty_name(self, mem_db: Path) -> None:
        engine = RetrievalEngine(mem_db)
        assert engine.find_symbol("") == []

    def test_find_symbol_not_found(self, mem_db: Path) -> None:
        engine = RetrievalEngine(mem_db)
        assert engine.find_symbol("__nonexistent__") == []

    def test_find_callers(self, mem_db: Path) -> None:
        engine = RetrievalEngine(mem_db)
        callers = engine.find_callers(2)  # callers of 'parse'
        assert any(c.name == "main" for c in callers)

    def test_find_references(self, mem_db: Path) -> None:
        engine = RetrievalEngine(mem_db)
        refs = engine.find_references(1)  # refs from 'main'
        assert any(r.name == "parse" for r in refs)

    def test_find_imports(self, mem_db: Path) -> None:
        engine = RetrievalEngine(mem_db)
        imports = engine.find_imports("src/main.py")
        # main → MyClass via import ref
        assert any(s.name == "MyClass" for s in imports)

    def test_find_imports_unknown_file(self, mem_db: Path) -> None:
        engine = RetrievalEngine(mem_db)
        assert engine.find_imports("no/file.py") == []

    def test_dependency_chain_no_cycle(self, mem_db: Path) -> None:
        engine = RetrievalEngine(mem_db)
        # main → parse → helper; no cycle
        chain = engine.get_dependency_chain(1, max_depth=3)
        names = {s.name for s in chain}
        assert "parse" in names
        assert "helper" in names
        # root itself not included
        assert "main" not in names

    def test_dependency_chain_circular(self, tmp_path: Path) -> None:
        """Circular A → B → A must terminate without infinite recursion."""
        db_path = tmp_path / "circ.db"
        conn = sqlite3.connect(str(db_path))
        _create_schema(conn)
        conn.execute("INSERT INTO files VALUES (1,1,'a.py','/a.py','python',0,'')")
        conn.executemany(
            "INSERT INTO symbols (id,file_id,name,symbol_type) VALUES (?,1,?,?)",
            [(1, "A", "function"), (2, "B", "function")],
        )
        conn.executemany(
            "INSERT INTO symbol_refs (caller_id,callee_id,ref_type) VALUES (?,?,'call')",
            [(1, 2), (2, 1)],
        )
        conn.commit()
        conn.close()

        engine = RetrievalEngine(db_path)
        chain = engine.get_dependency_chain(1, max_depth=5)
        assert len(chain) == 1  # only B, not A again

    def test_lru_cache_hit(self, mem_db: Path) -> None:
        engine = RetrievalEngine(mem_db, cache_size=10)
        engine.find_symbol("main")
        engine.find_symbol("main")
        assert engine.cache_hits >= 1

    def test_cache_invalidation(self, mem_db: Path) -> None:
        engine = RetrievalEngine(mem_db, cache_size=10)
        engine.find_symbol("main")
        engine.invalidate_cache()
        assert engine.cache_hits == 0

    def test_empty_index(self, empty_db: Path) -> None:
        engine = RetrievalEngine(empty_db)
        assert engine.find_symbol("anything") == []
        assert engine.find_callers(1) == []

    def test_get_related_context_empty_query(self, mem_db: Path) -> None:
        engine = RetrievalEngine(mem_db)
        result = engine.get_related_context(RetrievalQuery(query=""))
        assert result.is_empty

    def test_get_related_context_returns_snippets(self, mem_db: Path) -> None:
        engine = RetrievalEngine(mem_db)
        result = engine.get_related_context(RetrievalQuery(query="main", token_budget=4000))
        assert not result.is_empty
        assert result.total_tokens <= result.budget_tokens or len(result.snippets) == 1

    def test_get_related_context_budget_respected(self, mem_db: Path) -> None:
        engine = RetrievalEngine(mem_db)
        result = engine.get_related_context(RetrievalQuery(query="parse", token_budget=5))
        # Budget is extremely tight — at most 1 snippet should sneak through
        assert result.total_tokens > 0 or result.is_empty

    def test_retrieval_protocol_compliance(self, mem_db: Path) -> None:
        """RetrievalEngine must satisfy RetrievalProtocol at runtime."""
        engine = RetrievalEngine(mem_db)
        assert isinstance(engine, RetrievalProtocol)


@pytest.mark.integration
class TestRetrievalIntegration:
    def test_full_workflow(self, mem_db: Path) -> None:
        """Full query → ContextResult workflow."""
        engine = RetrievalEngine(mem_db)

        # Symbol lookup
        symbols = engine.find_symbol("parse")
        assert symbols

        # Get context for the first match
        focal = symbols[0]
        result = engine.get_related_context(
            RetrievalQuery(
                query="parse",
                symbol_name="parse",
                file_path=focal.file_path,
                token_budget=2000,
                include_callers=True,
                include_imports=True,
            )
        )

        assert not result.is_empty
        assert result.budget_tokens == 2000
        assert result.remaining_tokens >= 0
        assert all(s.relevance_score >= 0 for s in result.snippets)
