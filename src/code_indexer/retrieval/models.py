"""Data models for retrieval results and queries."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SymbolResult:
    """A single symbol retrieved from the index.

    Attributes:
        id: Primary key in the symbols table
        name: Short symbol name (e.g. 'parse')
        qualified_name: Fully qualified name (e.g. 'code_indexer.parsers.parse')
        symbol_type: One of 'function', 'class', 'method', 'variable', 'import'
        file_path: Relative path of the file containing the symbol
        language: Programming language of the file
        line_start: First line of the symbol definition (1-based)
        line_end: Last line of the symbol definition (1-based)
        signature: Function/class signature string
        docstring: First paragraph of the docstring if available
        relevance_score: Ranking score assigned by the retrieval engine
    """

    id: int
    name: str
    symbol_type: str
    file_path: str
    language: str
    qualified_name: Optional[str] = None
    line_start: Optional[int] = None
    line_end: Optional[int] = None
    signature: Optional[str] = None
    docstring: Optional[str] = None
    relevance_score: float = 0.0


@dataclass
class FileResult:
    """A file entry retrieved from the index.

    Attributes:
        id: Primary key in the files table
        relative_path: Path relative to the repository root
        absolute_path: Absolute filesystem path
        language: Detected programming language
        size: File size in bytes
        mtime: ISO-format modification timestamp
    """

    id: int
    relative_path: str
    absolute_path: str
    language: str
    size: int
    mtime: str


@dataclass
class ContextSnippet:
    """One ranked code snippet included in a ContextResult.

    Attributes:
        file_path: Relative path of the source file
        language: Programming language
        line_start: First line of the snippet (None if unknown)
        line_end: Last line of the snippet (None if unknown)
        content: Source text of the snippet (empty if not yet loaded)
        symbol_name: Name of the focal symbol in this snippet
        relevance_score: Score that determined inclusion order
        token_estimate: Estimated token count for this snippet
    """

    file_path: str
    language: str
    relevance_score: float
    token_estimate: int
    line_start: Optional[int] = None
    line_end: Optional[int] = None
    content: str = ""
    symbol_name: Optional[str] = None


@dataclass
class ContextResult:
    """The assembled minimal context returned to an AI agent.

    Attributes:
        query: Original query string
        snippets: Ranked snippets within the token budget
        total_tokens: Total estimated tokens across all included snippets
        budget_tokens: Token budget that was enforced
        remaining_tokens: Budget minus total_tokens
        dropped_count: Number of candidates dropped due to budget exhaustion
    """

    query: str
    snippets: list[ContextSnippet]
    total_tokens: int
    budget_tokens: int
    remaining_tokens: int
    dropped_count: int

    @property
    def is_empty(self) -> bool:
        """Return True when no snippets were included."""
        return len(self.snippets) == 0

    @property
    def was_truncated(self) -> bool:
        """Return True when at least one candidate was dropped."""
        return self.dropped_count > 0


@dataclass
class RetrievalQuery:
    """Structured query for the retrieval engine.

    Attributes:
        query: Free-text or symbol name to search for
        symbol_name: Exact symbol name to target (overrides FTS when set)
        file_path: Restrict results to this file
        language_filter: Restrict results to this language
        symbol_types: Restrict to specific symbol types
        max_depth: Maximum hops for dependency traversal
        token_budget: Maximum tokens for the assembled context
        include_callers: Whether to include calling symbols
        include_imports: Whether to include import chain symbols
    """

    query: str
    symbol_name: Optional[str] = None
    file_path: Optional[str] = None
    language_filter: Optional[str] = None
    symbol_types: Optional[list[str]] = None
    max_depth: int = 2
    token_budget: int = 8_000
    include_callers: bool = True
    include_imports: bool = True
    limit: int = 20
