"""Token estimation utilities.

The default estimator uses ``len(text) // 4`` as a fast, dependency-free
approximation (GPT-style tokens average ~4 characters each).

Swap in a real tokenizer by implementing TokenEstimator and injecting it
into the ContextBuilder or RetrievalEngine — no other code needs to change.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class TokenEstimator(Protocol):
    """Protocol for token counting implementations.

    Any callable that accepts a string and returns an int satisfies this
    protocol, so a lambda or a tiktoken wrapper both work.
    """

    def estimate(self, text: str) -> int:
        """Estimate the number of tokens in text.

        Args:
            text: Source text to estimate

        Returns:
            Estimated token count (always >= 1 for non-empty text)
        """
        ...


class CharDivFourEstimator:
    """Fast token estimator: ``max(1, len(text) // 4)``.

    This is a reasonable approximation for English-like source code.
    It intentionally over-estimates slightly to avoid budget overruns.
    Satisfies the TokenEstimator Protocol.
    """

    def estimate(self, text: str) -> int:
        """Estimate token count via character count divided by 4.

        Args:
            text: Source text to estimate

        Returns:
            Estimated token count (minimum 1 for non-empty strings, 0 for empty)
        """
        if not text:
            return 0
        return max(1, len(text) // 4)
