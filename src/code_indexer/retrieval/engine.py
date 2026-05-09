"""Retrieval engine: orchestrates repositories, ranking, and context assembly."""

from __future__ import annotations

import sqlite3
import time
from collections import OrderedDict
from pathlib import Path
from typing import Optional

from loguru import logger

from code_indexer.retrieval.context import ContextBuilder
from code_indexer.retrieval.models import (
    ContextResult,
    FileResult,
    RetrievalQuery,
    SymbolResult,
)
from code_indexer.retrieval.ranking import DefaultRankingStrategy, RankingContext, RankingStrategy
from code_indexer.retrieval.repositories import (
    FileRepository,
    ReferenceRepository,
    SymbolRepository,
)
from code_indexer.retrieval.tokens import CharDivFourEstimator, TokenEstimator
from code_indexer.utils.exceptions import RetrievalError

_SLOW_QUERY_MS = 100  # log warning when a query exceeds this threshold


class _LRUCache:
    """Simple in-memory LRU cache backed by an OrderedDict."""

    def __init__(self, max_size: int = 256) -> None:
        self._store: OrderedDict = OrderedDict()
        self.max_size = max_size
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Optional[list[SymbolResult]]:
        """Return cached value or None."""
        if key not in self._store:
            self.misses += 1
            return None
        self._store.move_to_end(key)
        self.hits += 1
        return self._store[key]

    def set(self, key: str, value: list[SymbolResult]) -> None:
        """Store value, evicting LRU entry if at capacity."""
        if key in self._store:
            self._store.move_to_end(key)
        self._store[key] = value
        if len(self._store) > self.max_size:
            self._store.popitem(last=False)

    def invalidate(self) -> None:
        """Clear all cached entries."""
        self._store.clear()


class RetrievalEngine:
    """Orchestrate symbol lookup, dependency traversal, and context assembly.

    Inject custom repositories, ranking strategy, or token estimator to
    override default behaviour without subclassing.

    Usage::

        engine = RetrievalEngine(db_path=Path("index.db"))
        results = engine.find_symbol("MyClass")
        context = engine.get_related_context(
            RetrievalQuery(query="MyClass", token_budget=4000)
        )
    """

    def __init__(
        self,
        db_path: Path,
        symbol_repo: Optional[SymbolRepository] = None,
        file_repo: Optional[FileRepository] = None,
        ref_repo: Optional[ReferenceRepository] = None,
        ranking_strategy: Optional[RankingStrategy] = None,
        token_estimator: Optional[TokenEstimator] = None,
        cache_size: int = 256,
    ) -> None:
        """Initialise the retrieval engine.

        Args:
            db_path: Path to the SQLite index database
            symbol_repo: Symbol data-access object (defaults to SymbolRepository)
            file_repo: File data-access object (defaults to FileRepository)
            ref_repo: Reference data-access object (defaults to ReferenceRepository)
            ranking_strategy: Ranking strategy (defaults to DefaultRankingStrategy)
            token_estimator: Token counter (defaults to CharDivFourEstimator)
            cache_size: Maximum number of entries in the symbol LRU cache
        """
        self._db_path = db_path
        self._symbol_repo = symbol_repo or SymbolRepository()
        self._file_repo = file_repo or FileRepository()
        self._ref_repo = ref_repo or ReferenceRepository()
        self._ranker: RankingStrategy = ranking_strategy or DefaultRankingStrategy()
        estimator: TokenEstimator = token_estimator or CharDivFourEstimator()
        self._context_builder = ContextBuilder(estimator=estimator)
        self._cache = _LRUCache(max_size=cache_size)

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        """Open and return a new SQLite connection.

        Raises:
            RetrievalError: If the database file cannot be opened
        """
        try:
            conn = sqlite3.connect(str(self._db_path))
            conn.row_factory = sqlite3.Row
            return conn
        except sqlite3.Error as e:
            raise RetrievalError(f"Cannot open index database: {self._db_path}: {e}") from e

    def invalidate_cache(self) -> None:
        """Invalidate the symbol lookup cache (call after re-indexing)."""
        self._cache.invalidate()
        logger.debug("Symbol cache invalidated")

    @property
    def cache_hits(self) -> int:
        """Number of cache hits since engine creation."""
        return self._cache.hits

    @property
    def cache_misses(self) -> int:
        """Number of cache misses since engine creation."""
        return self._cache.misses

    # ------------------------------------------------------------------
    # Core retrieval operations
    # ------------------------------------------------------------------

    def find_symbol(
        self,
        name: str,
        symbol_types: Optional[list[str]] = None,
        language: Optional[str] = None,
    ) -> list[SymbolResult]:
        """Find symbols by name (exact, prefix, substring).

        Results are cached by (name, symbol_types, language) key.

        Args:
            name: Symbol name to search
            symbol_types: Optional list of symbol types to restrict to
            language: Optional language filter

        Returns:
            List of SymbolResult ordered by match quality
        """
        if not name:
            return []

        cache_key = f"sym:{name}:{symbol_types}:{language}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        t0 = time.monotonic()
        try:
            with self._connect() as conn:
                results = self._symbol_repo.find_by_name(conn, name, symbol_types, language)
        except RetrievalError:
            raise
        except Exception as e:
            raise RetrievalError(f"find_symbol failed: {e}") from e
        finally:
            elapsed_ms = (time.monotonic() - t0) * 1000
            if elapsed_ms > _SLOW_QUERY_MS:
                logger.warning(f"Slow query find_symbol({name!r}): {elapsed_ms:.1f}ms")

        self._cache.set(cache_key, results)
        return results

    def find_references(self, symbol_id: int) -> list[SymbolResult]:
        """Find symbols referenced (called) by the given symbol.

        Args:
            symbol_id: Primary key of the caller symbol

        Returns:
            List of referenced SymbolResult
        """
        t0 = time.monotonic()
        try:
            with self._connect() as conn:
                return self._symbol_repo.find_callees(conn, symbol_id)
        except Exception as e:
            raise RetrievalError(f"find_references failed for id={symbol_id}: {e}") from e
        finally:
            _log_slow(t0, f"find_references({symbol_id})")

    def find_callers(self, symbol_id: int) -> list[SymbolResult]:
        """Find symbols that call the given symbol.

        Args:
            symbol_id: Primary key of the callee symbol

        Returns:
            List of caller SymbolResult
        """
        t0 = time.monotonic()
        try:
            with self._connect() as conn:
                return self._symbol_repo.find_callers(conn, symbol_id)
        except Exception as e:
            raise RetrievalError(f"find_callers failed for id={symbol_id}: {e}") from e
        finally:
            _log_slow(t0, f"find_callers({symbol_id})")

    def find_imports(self, file_path: str) -> list[SymbolResult]:
        """Find all symbols imported by a file.

        Args:
            file_path: Relative path of the importing file

        Returns:
            List of imported SymbolResult (empty if file not indexed)
        """
        t0 = time.monotonic()
        try:
            with self._connect() as conn:
                file_result = self._file_repo.find_by_path(conn, file_path)
                if file_result is None:
                    return []
                return self._ref_repo.find_imports_for_file(conn, file_result.id)
        except RetrievalError:
            raise
        except Exception as e:
            raise RetrievalError(f"find_imports failed for {file_path!r}: {e}") from e
        finally:
            _log_slow(t0, f"find_imports({file_path!r})")

    def search_code(self, query: str, limit: int = 20) -> list[SymbolResult]:
        """Full-text search across symbol names, signatures, and docstrings.

        Args:
            query: FTS5 query string
            limit: Maximum results

        Returns:
            List of matching SymbolResult (unranked — apply ranking separately)
        """
        if not query:
            return []

        t0 = time.monotonic()
        try:
            with self._connect() as conn:
                return self._symbol_repo.search_fts(conn, query, limit)
        except RetrievalError:
            raise
        except Exception as e:
            raise RetrievalError(f"search_code failed: {e}") from e
        finally:
            _log_slow(t0, f"search_code({query!r})")

    def get_dependency_chain(
        self,
        symbol_id: int,
        max_depth: int = 2,
    ) -> list[SymbolResult]:
        """Traverse the dependency graph from a symbol up to max_depth hops.

        Uses a visited set to prevent infinite loops on circular references.

        Args:
            symbol_id: Starting symbol ID
            max_depth: Maximum traversal depth

        Returns:
            Flat list of all reachable dependency symbols (excluding the root)
        """
        visited: set[int] = {symbol_id}
        results: list[SymbolResult] = []

        try:
            with self._connect() as conn:
                self._traverse(conn, symbol_id, max_depth, visited, results)
        except RetrievalError:
            raise
        except Exception as e:
            raise RetrievalError(f"get_dependency_chain failed for id={symbol_id}: {e}") from e

        return results

    def _traverse(
        self,
        conn: sqlite3.Connection,
        symbol_id: int,
        depth: int,
        visited: set[int],
        results: list[SymbolResult],
    ) -> None:
        """Recursive DFS dependency traversal.

        Args:
            conn: Active SQLite connection
            symbol_id: Current symbol being expanded
            depth: Remaining depth budget
            visited: Set of already-visited symbol IDs (prevents cycles)
            results: Accumulator for discovered symbols
        """
        if depth == 0:
            return

        for dep in self._symbol_repo.find_callees(conn, symbol_id):
            if dep.id in visited:
                continue
            visited.add(dep.id)
            results.append(dep)
            self._traverse(conn, dep.id, depth - 1, visited, results)

    def get_related_context(self, query: RetrievalQuery) -> ContextResult:
        """Assemble the minimal ContextResult for an AI agent query.

        Strategy:
        1. Locate focal symbols (FTS5 + exact match, merged & deduplicated)
        2. Add direct callees (references)
        3. Optionally add callers
        4. Optionally add import chain
        5. Rank all candidates
        6. Fill token budget from highest score down

        Args:
            query: Structured retrieval query

        Returns:
            ContextResult with ranked snippets within the token budget
        """
        if not query.query and not query.symbol_name:
            return _empty_result(query)

        t0 = time.monotonic()
        candidates: list[SymbolResult] = []
        seen_ids: set[int] = set()

        def add(symbols: list[SymbolResult]) -> None:
            for s in symbols:
                if s.id not in seen_ids:
                    seen_ids.add(s.id)
                    candidates.append(s)

        try:
            # 1. Focal symbols
            search_term = query.symbol_name or query.query
            add(self.find_symbol(search_term, query.symbol_types, query.language_filter))

            if not candidates:
                add(self.search_code(search_term, limit=query.limit))

            direct_ref_ids: set[int] = set()

            # 2. Direct references (callees)
            for focal in list(candidates):
                refs = self.find_references(focal.id)
                direct_ref_ids.update(r.id for r in refs)
                add(refs)

            # 3. Callers
            if query.include_callers:
                for focal in list(candidates[:5]):  # limit caller expansion
                    add(self.find_callers(focal.id))

            # 4. Dependency chain
            for focal in list(candidates[:3]):
                add(self.get_dependency_chain(focal.id, query.max_depth))

            # 5. Imports
            if query.include_imports and query.file_path:
                add(self.find_imports(query.file_path))

        except RetrievalError:
            raise
        except Exception as e:
            raise RetrievalError(f"get_related_context failed: {e}") from e
        finally:
            _log_slow(t0, f"get_related_context({query.query!r})")

        focal_file = candidates[0].file_path if candidates else query.file_path
        ctx = RankingContext(
            query=query.query,
            focal_file=focal_file,
            direct_ref_ids=direct_ref_ids,
        )
        ranked = self._ranker.rank(candidates, ctx)
        return self._context_builder.build(ranked, query)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _log_slow(t0: float, label: str) -> None:
    elapsed_ms = (time.monotonic() - t0) * 1000
    if elapsed_ms > _SLOW_QUERY_MS:
        logger.warning(f"Slow query {label}: {elapsed_ms:.1f}ms")


def _empty_result(query: RetrievalQuery) -> ContextResult:
    return ContextResult(
        query=query.query,
        snippets=[],
        total_tokens=0,
        budget_tokens=query.token_budget,
        remaining_tokens=query.token_budget,
        dropped_count=0,
    )
