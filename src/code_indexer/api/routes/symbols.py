"""API routes for symbol lookup and search."""
from __future__ import annotations

from pathlib import Path
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from code_indexer.retrieval.engine import RetrievalEngine
from code_indexer.retrieval.models import RetrievalQuery, SymbolResult
from code_indexer.utils.config import settings

router = APIRouter()


# ------------------------------------------------------------------
# Response schemas
# ------------------------------------------------------------------

class SymbolResponse(BaseModel):
    id: int
    name: str
    qualified_name: Optional[str]
    symbol_type: str
    file_path: str
    language: str
    line_start: Optional[int]
    line_end: Optional[int]
    signature: Optional[str]
    docstring: Optional[str]
    relevance_score: float = 0.0


class ContextSnippetResponse(BaseModel):
    file_path: str
    language: str
    symbol_name: Optional[str]
    qualified_name: Optional[str]
    symbol_type: Optional[str]
    line_start: Optional[int]
    line_end: Optional[int]
    relevance_score: float
    token_estimate: int


class ContextResponse(BaseModel):
    query: str
    snippets: list[ContextSnippetResponse]
    total_tokens: int
    budget_tokens: int
    remaining_tokens: int
    dropped_count: int


# ------------------------------------------------------------------
# Dependency
# ------------------------------------------------------------------

def _get_engine() -> RetrievalEngine:
    db_path = Path(settings.database_url.replace("sqlite:///", ""))
    return RetrievalEngine(db_path=db_path)


# ------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------

@router.get("/symbols", response_model=list[SymbolResponse], summary="Search symbols by name")
async def search_symbols(
    q: str = Query(..., description="Symbol name (exact, prefix, or substring)"),
    symbol_type: Optional[str] = Query(None, description="Filter by type: function|class|method|variable|import"),
    language: Optional[str] = Query(None, description="Filter by language"),
    engine: RetrievalEngine = Depends(_get_engine),
) -> list[SymbolResponse]:
    """Find symbols by name with optional type and language filters."""
    types = [symbol_type] if symbol_type else None
    results = engine.find_symbol(q, symbol_types=types, language=language)
    return [_symbol_to_response(s) for s in results]


@router.get("/symbols/search", response_model=list[SymbolResponse], summary="Full-text search symbols")
async def fts_search(
    q: str = Query(..., description="FTS5 query string"),
    limit: int = Query(20, ge=1, le=100),
    engine: RetrievalEngine = Depends(_get_engine),
) -> list[SymbolResponse]:
    """Full-text search across symbol names, signatures, and docstrings."""
    results = engine.search_code(q, limit=limit)
    return [_symbol_to_response(s) for s in results]


@router.get("/symbols/{symbol_id}", response_model=SymbolResponse, summary="Get symbol by ID")
async def get_symbol(
    symbol_id: int,
    engine: RetrievalEngine = Depends(_get_engine),
) -> SymbolResponse:
    """Fetch a single symbol by its primary key."""
    with engine._connect() as conn:
        result = engine._symbol_repo.find_by_id(conn, symbol_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Symbol {symbol_id} not found")
    return _symbol_to_response(result)


@router.get("/symbols/{symbol_id}/references", response_model=list[SymbolResponse], summary="Get symbols called by this symbol")
async def get_references(
    symbol_id: int,
    engine: RetrievalEngine = Depends(_get_engine),
) -> list[SymbolResponse]:
    """Return all symbols that the given symbol calls or references."""
    results = engine.find_references(symbol_id)
    return [_symbol_to_response(s) for s in results]


@router.get("/symbols/{symbol_id}/callers", response_model=list[SymbolResponse], summary="Get symbols that call this symbol")
async def get_callers(
    symbol_id: int,
    engine: RetrievalEngine = Depends(_get_engine),
) -> list[SymbolResponse]:
    """Return all symbols that call the given symbol."""
    results = engine.find_callers(symbol_id)
    return [_symbol_to_response(s) for s in results]


@router.get("/symbols/{symbol_id}/dependencies", response_model=list[SymbolResponse], summary="Traverse dependency graph")
async def get_dependencies(
    symbol_id: int,
    max_depth: int = Query(2, ge=1, le=5),
    engine: RetrievalEngine = Depends(_get_engine),
) -> list[SymbolResponse]:
    """Traverse the dependency graph from a symbol up to max_depth hops."""
    results = engine.get_dependency_chain(symbol_id, max_depth=max_depth)
    return [_symbol_to_response(s) for s in results]


@router.get("/context", response_model=ContextResponse, summary="Get minimal context for an AI query")
async def get_context(
    q: str = Query(..., description="Query or symbol name"),
    symbol_name: Optional[str] = Query(None),
    language: Optional[str] = Query(None),
    token_budget: int = Query(8000, ge=500, le=100000),
    include_callers: bool = Query(True),
    include_imports: bool = Query(True),
    max_depth: int = Query(2, ge=1, le=5),
    engine: RetrievalEngine = Depends(_get_engine),
) -> ContextResponse:
    """Assemble a ranked, token-budgeted context for an AI agent query."""
    query = RetrievalQuery(
        query=q,
        symbol_name=symbol_name,
        language_filter=language,
        token_budget=token_budget,
        include_callers=include_callers,
        include_imports=include_imports,
        max_depth=max_depth,
    )
    ctx = engine.get_related_context(query)
    snippets = [
        ContextSnippetResponse(
            file_path=s.file_path,
            language=s.language,
            symbol_name=s.symbol_name,
            qualified_name=None,
            symbol_type=None,
            line_start=s.line_start,
            line_end=s.line_end,
            relevance_score=s.relevance_score,
            token_estimate=s.token_estimate,
        )
        for s in ctx.snippets
    ]
    return ContextResponse(
        query=ctx.query,
        snippets=snippets,
        total_tokens=ctx.total_tokens,
        budget_tokens=ctx.budget_tokens,
        remaining_tokens=ctx.remaining_tokens,
        dropped_count=ctx.dropped_count,
    )


# ------------------------------------------------------------------
# Helper
# ------------------------------------------------------------------

def _symbol_to_response(s: SymbolResult) -> SymbolResponse:
    return SymbolResponse(
        id=s.id,
        name=s.name,
        qualified_name=s.qualified_name,
        symbol_type=s.symbol_type,
        file_path=s.file_path,
        language=s.language,
        line_start=s.line_start,
        line_end=s.line_end,
        signature=s.signature,
        docstring=s.docstring,
        relevance_score=s.relevance_score,
    )
