"""Extractor package — symbol and reference extraction from parsed ASTs."""
from code_indexer.extractor.base import BaseExtractor, ExtractionContext
from code_indexer.extractor.models import ExtractionResult, ExtractedSymbol, Reference
from code_indexer.extractor.registry import ExtractorRegistry

__all__ = [
    "BaseExtractor",
    "ExtractionContext",
    "ExtractionResult",
    "ExtractedSymbol",
    "Reference",
    "ExtractorRegistry",
]
