"""Row-level dataclasses for the indexer persistence layer."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RepositoryRecord:
    """One row from the ``repositories`` table.

    Attributes:
        id: Primary key (0 when not yet persisted).
        root_path: Absolute path to the repository root.
        name: Human-readable repository name.
        created_at: ISO-8601 timestamp string.
        updated_at: ISO-8601 timestamp string.
    """

    id: int
    root_path: str
    name: str
    created_at: str
    updated_at: str


@dataclass
class FileRecord:
    """One row from the ``files`` table.

    Attributes:
        id: Primary key (0 when not yet persisted).
        repo_id: Foreign key into ``repositories``.
        relative_path: Path relative to the repository root.
        absolute_path: Absolute filesystem path.
        language: Language string (e.g. ``python``).
        size: File size in bytes.
        mtime: Last-modified timestamp string from FileMetadata.
        hash: Optional SHA-256 hex digest for change detection.
    """

    id: int
    repo_id: int
    relative_path: str
    absolute_path: str
    language: str
    size: int
    mtime: str
    hash: str | None = None
