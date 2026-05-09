"""Retrieval Protocol for agent-layer decoupling.

AI agent code should import RetrievalProtocol and type-hint against it,
never against the concrete RetrievalEngine.  This mirrors the ScannerProtocol
pattern established in code_indexer.scanner.protocols.
"""

from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

from code_indexer.retrieval.models import ContextResult, FileResult, RetrievalQuery, SymbolResult


@runtime_checkable
class RetrievalProtocol(Protocol):
    """Interface the AI agent layer uses to retrieve code context.

    Any object exposing these five methods is a valid retrieval engine —
    whether it is the real RetrievalEngine, a mock, or a future remote
    retrieval service.
    """

    def find_symbol(
        self,
        name: str,
        symbol_types: Optional[list[str]] = None,
        language: Optional[str] = None,
    ) -> list[SymbolResult]:
        """Find symbols by name.

        Args:
            name: Symbol name (exact, prefix, or substring)
            symbol_types: Optional type filter list
            language: Optional language filter

        Returns:
            Matching symbols ordered by relevance
        """
        ...

    def find_references(self, symbol_id: int) -> list[SymbolResult]:
        """Find symbols referenced by the given symbol.

        Args:
            symbol_id: Caller symbol primary key

        Returns:
            List of referenced SymbolResult
        """
        ...

    def find_callers(self, symbol_id: int) -> list[SymbolResult]:
        """Find symbols that call the given symbol.

        Args:
            symbol_id: Callee symbol primary key

        Returns:
            List of caller SymbolResult
        """
        ...

    def find_imports(self, file_path: str) -> list[SymbolResult]:
        """Find all symbols imported by a file.

        Args:
            file_path: Relative path of the importing file

        Returns:
            List of imported SymbolResult
        """
        ...

    def search_code(self, query: str, limit: int = 20) -> list[SymbolResult]:
        """Full-text search across symbol names, signatures, and docstrings.

        Args:
            query: Search query string
            limit: Maximum number of results

        Returns:
            Matching symbols (unranked)
        """
        ...

    def get_related_context(self, query: RetrievalQuery) -> ContextResult:
        """Assemble minimal context for an AI agent query.

        Args:
            query: Structured retrieval query with token budget

        Returns:
            ContextResult with ranked, budget-limited snippets
        """
        ...

    def get_dependency_chain(
        self, symbol_id: int, max_depth: int = 2
    ) -> list[SymbolResult]:
        """Traverse the dependency graph from a symbol.

        Args:
            symbol_id: Starting symbol ID
            max_depth: Maximum traversal depth

        Returns:
            All reachable dependency symbols (excluding the root)
        """
        ...
