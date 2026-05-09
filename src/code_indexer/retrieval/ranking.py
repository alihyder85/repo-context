"""Relevance ranking for retrieval results.

Scoring rules (additive):
  +1.0  exact symbol name match
  +0.7  prefix match
  +0.4  substring match
  +0.5  direct reference to focal symbol
  +0.3  same file as focal
  +0.1  same directory as focal
  +0.1  recently modified (within 30 days)
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional, Protocol, runtime_checkable

from code_indexer.retrieval.models import SymbolResult


@dataclass
class RankingContext:
    """Context passed to ranking strategies.

    Attributes:
        query: Original query / symbol name being searched
        focal_file: Relative path of the file the query originates from
        direct_ref_ids: Symbol IDs that are direct references to the focal
        now: Reference time for recency scoring (defaults to UTC now)
    """

    query: str
    focal_file: Optional[str] = None
    direct_ref_ids: Optional[set[int]] = None
    now: datetime = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.now is None:
            self.now = datetime.now(tz=timezone.utc)
        if self.direct_ref_ids is None:
            self.direct_ref_ids = set()


@runtime_checkable
class RankingStrategy(Protocol):
    """Protocol for pluggable ranking strategies.

    Implementors receive a list of SymbolResult and a RankingContext and
    must return the same results sorted by descending relevance_score.
    The scores are written onto each result in-place.
    """

    def rank(
        self,
        results: list[SymbolResult],
        context: RankingContext,
    ) -> list[SymbolResult]:
        """Sort results by relevance, mutating relevance_score in-place.

        Args:
            results: Candidate symbols to rank
            context: Query context for scoring decisions

        Returns:
            The same list sorted by descending relevance_score
        """
        ...


class RelevanceScorer:
    """Compute additive relevance scores for a single SymbolResult."""

    _RECENCY_WINDOW = timedelta(days=30)

    def score(self, symbol: SymbolResult, context: RankingContext) -> float:
        """Compute the relevance score for one symbol.

        Args:
            symbol: Candidate symbol
            context: Query context

        Returns:
            Float score (higher = more relevant)
        """
        score = 0.0
        query_lower = context.query.lower()
        name_lower = symbol.name.lower()

        # Name match quality
        if name_lower == query_lower:
            score += 1.0
        elif name_lower.startswith(query_lower):
            score += 0.7
        elif query_lower in name_lower:
            score += 0.4

        # Direct reference
        if context.direct_ref_ids and symbol.id in context.direct_ref_ids:
            score += 0.5

        # File proximity
        if context.focal_file:
            focal_dir = os.path.dirname(context.focal_file)
            symbol_dir = os.path.dirname(symbol.file_path)

            if symbol.file_path == context.focal_file:
                score += 0.3
            elif symbol_dir == focal_dir:
                score += 0.1

        return score


class DefaultRankingStrategy:
    """Default ranking strategy using additive RelevanceScorer rules.

    Satisfies the RankingStrategy Protocol.
    """

    def __init__(self) -> None:
        self._scorer = RelevanceScorer()

    def rank(
        self,
        results: list[SymbolResult],
        context: RankingContext,
    ) -> list[SymbolResult]:
        """Score and sort results by descending relevance.

        Args:
            results: Candidate symbols to rank
            context: Query context for scoring decisions

        Returns:
            Sorted list with relevance_score populated on each item
        """
        for symbol in results:
            symbol.relevance_score = self._scorer.score(symbol, context)

        return sorted(results, key=lambda s: s.relevance_score, reverse=True)
