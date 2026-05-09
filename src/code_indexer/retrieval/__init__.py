"""Token-efficient code retrieval for AI agents."""

from code_indexer.retrieval.context import ContextBuilder
from code_indexer.retrieval.engine import RetrievalEngine
from code_indexer.retrieval.models import (
    ContextResult,
    ContextSnippet,
    FileResult,
    RetrievalQuery,
    SymbolResult,
)
from code_indexer.retrieval.protocols import RetrievalProtocol
from code_indexer.retrieval.ranking import (
    DefaultRankingStrategy,
    RankingContext,
    RankingStrategy,
    RelevanceScorer,
)
from code_indexer.retrieval.repositories import (
    FileRepository,
    ReferenceRepository,
    SymbolRepository,
)
from code_indexer.retrieval.tokens import CharDivFourEstimator, TokenEstimator

__all__ = [
    # Engine
    "RetrievalEngine",
    # Protocol
    "RetrievalProtocol",
    # Models
    "SymbolResult",
    "FileResult",
    "ContextSnippet",
    "ContextResult",
    "RetrievalQuery",
    # Ranking
    "RelevanceScorer",
    "RankingContext",
    "RankingStrategy",
    "DefaultRankingStrategy",
    # Repositories
    "SymbolRepository",
    "FileRepository",
    "ReferenceRepository",
    # Context
    "ContextBuilder",
    # Tokens
    "TokenEstimator",
    "CharDivFourEstimator",
]
