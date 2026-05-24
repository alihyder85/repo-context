"""Indexer package — SQLite persistence layer."""
from code_indexer.indexer.models import FileRecord, RepositoryRecord
from code_indexer.indexer.protocols import IndexerProtocol
from code_indexer.indexer.reindexer import IncrementalReindexer, ReindexStats
from code_indexer.indexer.schema import create_tables, migrate
from code_indexer.indexer.writer import IndexWriter

__all__ = [
    "IndexWriter",
    "IndexerProtocol",
    "IncrementalReindexer",
    "ReindexStats",
    "RepositoryRecord",
    "FileRecord",
    "create_tables",
    "migrate",
]
