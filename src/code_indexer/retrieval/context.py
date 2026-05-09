"""Context builder: assemble a minimal ContextResult from ranked symbols.

Responsibilities:
- Deduplicate symbols (same ID appears only once)
- Convert SymbolResult → ContextSnippet with token estimation
- Fill from highest relevance downward until budget is exhausted
- Report exactly how many candidates were dropped
"""

from __future__ import annotations

from code_indexer.retrieval.models import (
    ContextResult,
    ContextSnippet,
    RetrievalQuery,
    SymbolResult,
)
from code_indexer.retrieval.tokens import CharDivFourEstimator, TokenEstimator


class ContextBuilder:
    """Assemble a ContextResult from a ranked list of SymbolResult.

    Usage::

        builder = ContextBuilder()
        result = builder.build(ranked_symbols, query)
    """

    def __init__(self, estimator: TokenEstimator | None = None) -> None:
        """Initialise the context builder.

        Args:
            estimator: Token estimator to use. Defaults to CharDivFourEstimator.
        """
        self._estimator: TokenEstimator = estimator or CharDivFourEstimator()

    def build(
        self,
        ranked_symbols: list[SymbolResult],
        query: RetrievalQuery,
    ) -> ContextResult:
        """Build a ContextResult from pre-ranked symbols.

        The caller is responsible for ranking ``ranked_symbols`` before
        passing them here.  This method only deduplicates, converts,
        and enforces the token budget.

        Args:
            ranked_symbols: Symbols sorted by descending relevance_score
            query: Original query (provides token_budget and query string)

        Returns:
            ContextResult with snippets within budget and metadata
        """
        seen_ids: set[int] = set()
        snippets: list[ContextSnippet] = []
        total_tokens = 0
        dropped_count = 0
        budget = query.token_budget

        for symbol in ranked_symbols:
            # Deduplicate
            if symbol.id in seen_ids:
                continue
            seen_ids.add(symbol.id)

            snippet = self._to_snippet(symbol)

            # If a single snippet already exceeds the full budget, include it
            # anyway as the first snippet (caller needs *something*), but
            # stop after that.
            if not snippets and snippet.token_estimate > budget:
                snippets.append(snippet)
                total_tokens += snippet.token_estimate
                # Everything else after this is dropped
                dropped_count += len(ranked_symbols) - 1
                break

            if total_tokens + snippet.token_estimate > budget:
                dropped_count += 1
                continue

            snippets.append(snippet)
            total_tokens += snippet.token_estimate

        return ContextResult(
            query=query.query,
            snippets=snippets,
            total_tokens=total_tokens,
            budget_tokens=budget,
            remaining_tokens=max(0, budget - total_tokens),
            dropped_count=dropped_count,
        )

    def _to_snippet(self, symbol: SymbolResult) -> ContextSnippet:
        """Convert a SymbolResult into a ContextSnippet.

        Uses the signature + docstring as the snippet content because full
        source lines are not available until the file is read by the caller.

        Args:
            symbol: Source symbol

        Returns:
            ContextSnippet with token estimate populated
        """
        parts: list[str] = []
        if symbol.signature:
            parts.append(symbol.signature)
        if symbol.docstring:
            parts.append(symbol.docstring)
        content = "\n".join(parts)

        return ContextSnippet(
            file_path=symbol.file_path,
            language=symbol.language,
            line_start=symbol.line_start,
            line_end=symbol.line_end,
            content=content,
            symbol_name=symbol.name,
            relevance_score=symbol.relevance_score,
            token_estimate=self._estimator.estimate(content),
        )
