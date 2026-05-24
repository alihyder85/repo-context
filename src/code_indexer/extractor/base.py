"""Abstract base class and context helper for extractors."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from code_indexer.extractor.models import ExtractionResult, ExtractedSymbol, Reference
from code_indexer.parsers.models import ParsedFile


@dataclass
class ExtractionContext:
    """Mutable state threaded through a single-file AST walk.

    Attributes:
        file_path: Relative file path string.
        language: Language string.
        scope_stack: Stack of qualified name fragments for current nesting.
        symbols: Accumulator for extracted symbols.
        references: Accumulator for extracted references.
    """

    file_path: str
    language: str
    scope_stack: list[str] = field(default_factory=list)
    symbols: list[ExtractedSymbol] = field(default_factory=list)
    references: list[Reference] = field(default_factory=list)

    @property
    def current_scope(self) -> str:
        """Return the current qualified scope, or file_path if at module level."""
        return ".".join(self.scope_stack) if self.scope_stack else self.file_path


class BaseExtractor(ABC):
    """ABC for stateless, thread-safe symbol/reference extractors.

    A single instance is created at startup and reused for every file of
    that language.  ``extract()`` must never raise.
    """

    @abstractmethod
    def extract(self, parsed_file: ParsedFile) -> ExtractionResult:
        """Extract symbols and references from *parsed_file*.

        Args:
            parsed_file: Parser output for the source file.

        Returns:
            ExtractionResult — never raises; errors go into ``.error``.
        """
