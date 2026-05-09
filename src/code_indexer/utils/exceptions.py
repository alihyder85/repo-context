"""Custom exceptions for the code indexer."""


class CodeIndexerError(Exception):
    """Base exception for code indexer errors."""
    pass


class ConfigurationError(CodeIndexerError):
    """Raised when there's a configuration error."""
    pass


class ScannerError(CodeIndexerError):
    """Raised when there's an error during repository scanning."""
    pass


class ParserError(CodeIndexerError):
    """Raised when there's an error during code parsing."""
    pass


class ExtractorError(CodeIndexerError):
    """Raised when there's an error during symbol extraction."""
    pass


class IndexerError(CodeIndexerError):
    """Raised when there's an error during indexing."""
    pass


class RetrievalError(CodeIndexerError):
    """Raised when there's an error during retrieval."""
    pass


class DatabaseError(CodeIndexerError):
    """Raised when there's a database error."""
    pass


class ValidationError(CodeIndexerError):
    """Raised when there's a validation error."""
    pass