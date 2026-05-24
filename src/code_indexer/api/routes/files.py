"""API routes for file lookup and per-file symbol listing."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from code_indexer.api.routes.symbols import SymbolResponse, _get_engine, _symbol_to_response
from code_indexer.retrieval.engine import RetrievalEngine

router = APIRouter()


class FileResponse(BaseModel):
    id: int
    relative_path: str
    absolute_path: str
    language: str
    size: int
    mtime: str


@router.get("/files", response_model=list[FileResponse], summary="List files by language")
async def list_files(
    language: Optional[str] = Query(None, description="Filter by language"),
    engine: RetrievalEngine = Depends(_get_engine),
) -> list[FileResponse]:
    """Return all indexed files, optionally filtered by language."""
    with engine._connect() as conn:
        if language:
            rows = engine._file_repo.find_by_language(conn, language)
        else:
            conn.row_factory = __import__("sqlite3").Row
            raw = conn.execute(
                "SELECT id, relative_path, absolute_path, language, size, mtime FROM files"
            ).fetchall()
            from code_indexer.retrieval.models import FileResult
            rows = [
                FileResult(
                    id=r["id"],
                    relative_path=r["relative_path"],
                    absolute_path=r["absolute_path"],
                    language=r["language"],
                    size=r["size"],
                    mtime=r["mtime"],
                )
                for r in raw
            ]
    return [_file_to_response(f) for f in rows]


@router.get("/files/{file_id}", response_model=FileResponse, summary="Get file by ID")
async def get_file(
    file_id: int,
    engine: RetrievalEngine = Depends(_get_engine),
) -> FileResponse:
    """Fetch a single file record by its primary key."""
    with engine._connect() as conn:
        result = engine._file_repo.find_by_id(conn, file_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"File {file_id} not found")
    return _file_to_response(result)


@router.get("/files/{file_id}/symbols", response_model=list[SymbolResponse], summary="List symbols in a file")
async def get_file_symbols(
    file_id: int,
    engine: RetrievalEngine = Depends(_get_engine),
) -> list[SymbolResponse]:
    """Return all symbols defined in the given file."""
    with engine._connect() as conn:
        file_result = engine._file_repo.find_by_id(conn, file_id)
        if file_result is None:
            raise HTTPException(status_code=404, detail=f"File {file_id} not found")
        symbols = engine._symbol_repo.find_by_file(conn, file_id)
    return [_symbol_to_response(s) for s in symbols]


@router.get("/files/{file_id}/imports", response_model=list[SymbolResponse], summary="List imports for a file")
async def get_file_imports(
    file_id: int,
    engine: RetrievalEngine = Depends(_get_engine),
) -> list[SymbolResponse]:
    """Return all symbols imported by the given file."""
    with engine._connect() as conn:
        file_result = engine._file_repo.find_by_id(conn, file_id)
        if file_result is None:
            raise HTTPException(status_code=404, detail=f"File {file_id} not found")
        imports = engine._ref_repo.find_imports_for_file(conn, file_id)
    return [_symbol_to_response(s) for s in imports]


def _file_to_response(f: object) -> FileResponse:
    return FileResponse(
        id=f.id,
        relative_path=f.relative_path,
        absolute_path=f.absolute_path,
        language=f.language,
        size=f.size,
        mtime=f.mtime,
    )
