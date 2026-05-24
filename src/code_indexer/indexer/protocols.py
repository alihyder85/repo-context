"""Runtime-checkable protocol for the indexer write API."""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from code_indexer.extractor.models import ExtractedSymbol, Reference
from code_indexer.scanner.models import FileMetadata


@runtime_checkable
class IndexerProtocol(Protocol):
    """Write interface consumed by IncrementalReindexer.

    All methods are transactional — each call either fully succeeds or
    raises ``DatabaseError`` without partial writes.
    """

    def write_repository(self, repo_root: str, name: str) -> int:
        """Upsert a repository row and return its primary key."""
        ...

    def write_file(self, file_meta: FileMetadata, repo_id: int) -> int:
        """Upsert a file row and return its primary key."""
        ...

    def write_symbols(self, symbols: list[ExtractedSymbol], file_id: int) -> list[int]:
        """Bulk-insert symbols for a file and return their primary keys."""
        ...

    def write_references(
        self, refs: list[Reference], symbol_id_map: dict[str, int]
    ) -> None:
        """Bulk-insert references, resolving callee names via symbol_id_map."""
        ...

    def delete_file(self, file_id: int) -> None:
        """Delete a file row (cascades to symbols and refs)."""
        ...

    def rebuild_fts(self) -> None:
        """Rebuild the FTS5 index from the symbols table."""
        ...
