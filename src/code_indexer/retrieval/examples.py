"""Example usage of the retrieval engine.

These examples assume an indexed SQLite database at 'index.db'.
Run the scanner + indexer phases first to populate the database.
"""

from __future__ import annotations

from pathlib import Path

from code_indexer.retrieval.engine import RetrievalEngine
from code_indexer.retrieval.models import RetrievalQuery
from code_indexer.retrieval.tokens import CharDivFourEstimator


def example_find_symbol() -> None:
    """Example: Locate a symbol by name."""
    engine = RetrievalEngine(Path("index.db"))
    results = engine.find_symbol("MyClass")

    for sym in results:
        print(f"{sym.symbol_type:10} {sym.name:30} {sym.file_path}:{sym.line_start}")


def example_find_callers() -> None:
    """Example: Who calls a given function?"""
    engine = RetrievalEngine(Path("index.db"))
    symbols = engine.find_symbol("parse")

    if symbols:
        callers = engine.find_callers(symbols[0].id)
        print(f"Callers of '{symbols[0].name}':")
        for c in callers:
            print(f"  {c.file_path}:{c.line_start}  {c.name}")


def example_dependency_chain() -> None:
    """Example: Traverse what a function depends on."""
    engine = RetrievalEngine(Path("index.db"))
    symbols = engine.find_symbol("main")

    if symbols:
        chain = engine.get_dependency_chain(symbols[0].id, max_depth=3)
        print(f"Dependencies of '{symbols[0].name}' (depth=3):")
        for dep in chain:
            print(f"  {dep.name} ({dep.symbol_type}) in {dep.file_path}")


def example_minimal_context() -> None:
    """Example: Build minimal context for an AI agent (core use-case)."""
    engine = RetrievalEngine(Path("index.db"))

    result = engine.get_related_context(
        RetrievalQuery(
            query="parse",
            symbol_name="parse",
            token_budget=4_000,
            max_depth=2,
            include_callers=True,
            include_imports=True,
        )
    )

    print(f"Context for query 'parse':")
    print(f"  Snippets:          {len(result.snippets)}")
    print(f"  Total tokens:      {result.total_tokens}")
    print(f"  Remaining budget:  {result.remaining_tokens}")
    print(f"  Dropped:           {result.dropped_count}")
    print()

    for i, snippet in enumerate(result.snippets, 1):
        print(f"  [{i}] score={snippet.relevance_score:.2f}  {snippet.file_path}:{snippet.line_start}")
        if snippet.content:
            preview = snippet.content[:120].replace("\n", " ")
            print(f"      {preview}")


def example_fts_search() -> None:
    """Example: Full-text search across symbol signatures and docstrings."""
    engine = RetrievalEngine(Path("index.db"))
    results = engine.search_code("token budget retrieval", limit=10)

    print("FTS results:")
    for sym in results:
        print(f"  {sym.name:30} {sym.file_path}")


def example_custom_token_estimator() -> None:
    """Example: Swap in a real tokenizer (e.g. tiktoken)."""
    # Uncomment and install tiktoken to use this:
    # import tiktoken
    # enc = tiktoken.get_encoding("cl100k_base")
    #
    # class TiktokenEstimator:
    #     def estimate(self, text: str) -> int:
    #         return len(enc.encode(text))
    #
    # engine = RetrievalEngine(Path("index.db"), token_estimator=TiktokenEstimator())

    # Default char/4 estimator
    engine = RetrievalEngine(Path("index.db"), token_estimator=CharDivFourEstimator())
    result = engine.get_related_context(RetrievalQuery(query="main", token_budget=2000))
    print(f"Tokens used: {result.total_tokens} / {result.budget_tokens}")


def example_cache_metrics() -> None:
    """Example: Inspect LRU cache performance."""
    engine = RetrievalEngine(Path("index.db"), cache_size=128)

    for _ in range(5):
        engine.find_symbol("parse")

    print(f"Cache hits:   {engine.cache_hits}")
    print(f"Cache misses: {engine.cache_misses}")

    engine.invalidate_cache()
    print("Cache invalidated.")


if __name__ == "__main__":
    # Uncomment to run:
    # example_find_symbol()
    # example_find_callers()
    # example_dependency_chain()
    # example_minimal_context()
    # example_fts_search()
    # example_custom_token_estimator()
    # example_cache_metrics()
    print("Retrieval examples — uncomment in __main__ to run")
